// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT license.

#include "linux_aligned_file_reader.h"
#include "qshape/baseline.h"

#include <cassert>
#include <cstdio>
#include <iostream>
#include "tsl/robin_map.h"
#include "utils.h"
#define MAX_EVENTS 1024

namespace
{
typedef struct io_event io_event_t;
typedef struct iocb iocb_t;

void execute_io(io_context_t ctx, int fd, std::vector<AlignedRead> &read_reqs, uint64_t n_retries = 0)
{
#ifdef DEBUG
    for (auto &req : read_reqs)
    {
        assert(IS_ALIGNED(req.len, 512));
        // std::cout << "request:"<<req.offset<<":"<<req.len << std::endl;
        assert(IS_ALIGNED(req.offset, 512));
        assert(IS_ALIGNED(req.buf, 512));
        // assert(malloc_usable_size(req.buf) >= req.len);
    }
#endif

    // break-up requests into chunks of size MAX_EVENTS each
    uint64_t n_iters = ROUND_UP(read_reqs.size(), MAX_EVENTS) / MAX_EVENTS;
    for (uint64_t iter = 0; iter < n_iters; iter++)
    {
        uint64_t n_ops = std::min((uint64_t)read_reqs.size() - (iter * MAX_EVENTS), (uint64_t)MAX_EVENTS);
        std::vector<iocb_t *> cbs(n_ops, nullptr);
        std::vector<io_event_t> evts(n_ops);
        std::vector<struct iocb> cb(n_ops);
        for (uint64_t j = 0; j < n_ops; j++)
        {
            io_prep_pread(cb.data() + j, fd, read_reqs[j + iter * MAX_EVENTS].buf, read_reqs[j + iter * MAX_EVENTS].len,
                          read_reqs[j + iter * MAX_EVENTS].offset);
        }

        // initialize `cbs` using `cb` array
        //

        for (uint64_t i = 0; i < n_ops; i++)
        {
            cbs[i] = cb.data() + i;
        }

        auto* q=qshape::current();
        const uint64_t first=q?q->next:0;
        // Reserve before submission: trace allocation must not unwind live DMA buffers.
        if(q&&qshape::config().trace)q->events.reserve(q->events.size()+2*n_ops);
        int64_t ret=io_submit(ctx,n_ops,cbs.data());
        if(ret<0)throw std::runtime_error("io_submit failed: "+std::to_string(ret));
        const uint64_t accepted=ret;
        if(q){
            const auto t=qshape::config().trace?qshape::now_ns():0;
            for(uint64_t j=0;j<accepted;++j){
                const auto& req=read_reqs[iter*MAX_EVENTS+j];
                ++q->submitted;q->bytes+=req.len;
                q->event(q->next++,req.offset,req.len,"IO_SUBMIT",0,t);
            }
        }
        uint64_t harvested=0;bool failed=accepted!=n_ops;
        while(harvested<accepted){
            ret=io_getevents(ctx,accepted-harvested,accepted-harvested,evts.data(),nullptr);
            if(ret==-EINTR)continue;
            // Cannot safely unwind if kernel ownership of buffers is unknown.
            if(ret<=0){std::cerr<<"fatal io_getevents failure "<<ret<<std::endl;std::abort();}
            const auto t=q&&qshape::config().trace?qshape::now_ns():0;
            for(int64_t j=0;j<ret;++j){
                const auto idx=static_cast<uint64_t>(evts[j].obj-cb.data());
                if(idx>=accepted)std::abort();
                const auto& req=read_reqs[iter*MAX_EVENTS+idx];
                const auto result=static_cast<int64_t>(evts[j].res);
                const bool bad=result!=static_cast<int64_t>(req.len)||evts[j].res2!=0;
                failed|=bad;
                if(q){++q->completed;if(bad)++q->errors;q->event(first+idx,req.offset,req.len,"IO_COMPLETE",result,t);}
            }
            harvested+=ret;
        }
        if(failed)throw std::runtime_error("partial submission or failed/short read");
        // disabled since req.buf could be an offset into another buf
        /*
        for (auto &req : read_reqs) {
          // corruption check
          assert(malloc_usable_size(req.buf) >= req.len);
        }
        */
    }
}
} // namespace

LinuxAlignedFileReader::LinuxAlignedFileReader()
{
    this->file_desc = -1;
}

LinuxAlignedFileReader::~LinuxAlignedFileReader()
{
    int64_t ret;
    // check to make sure file_desc is closed
    ret = ::fcntl(this->file_desc, F_GETFD);
    if (ret == -1)
    {
        if (errno != EBADF)
        {
            std::cerr << "close() not called" << std::endl;
            // close file desc
            ret = ::close(this->file_desc);
            // error checks
            if (ret == -1)
            {
                std::cerr << "close() failed; returned " << ret << ", errno=" << errno << ":" << ::strerror(errno)
                          << std::endl;
            }
        }
    }
}

io_context_t &LinuxAlignedFileReader::get_ctx()
{
    std::unique_lock<std::mutex> lk(ctx_mut);
    // perform checks only in DEBUG mode
    if (ctx_map.find(std::this_thread::get_id()) == ctx_map.end())
    {
        std::cerr << "bad thread access; returning -1 as io_context_t" << std::endl;
        return this->bad_ctx;
    }
    else
    {
        return ctx_map[std::this_thread::get_id()];
    }
}

void LinuxAlignedFileReader::register_thread()
{
    auto my_id = std::this_thread::get_id();
    std::unique_lock<std::mutex> lk(ctx_mut);
    if (ctx_map.find(my_id) != ctx_map.end())
    {
        std::cerr << "multiple calls to register_thread from the same thread" << std::endl;
        return;
    }
    io_context_t ctx = 0;
    int ret = io_setup(MAX_EVENTS, &ctx);
    if (ret != 0)
    {
        if (ret == -EAGAIN)
        {
            std::cerr << "io_setup() failed with EAGAIN: Consider increasing /proc/sys/fs/aio-max-nr" << std::endl;
        }
        else
        {
            std::cerr << "io_setup() failed; returned " << ret << ": " << ::strerror(-ret) << std::endl;
        }
    }
    else
    {
        diskann::cout << "allocating ctx: " << ctx << " to thread-id:" << my_id << std::endl;
        ctx_map[my_id] = ctx;
    }
}

void LinuxAlignedFileReader::deregister_thread()
{
    auto my_id = std::this_thread::get_id();
    std::unique_lock<std::mutex> lk(ctx_mut);
    assert(ctx_map.find(my_id) != ctx_map.end());

    lk.unlock();
    io_context_t ctx = this->get_ctx();
    io_destroy(ctx);
    //  assert(ret == 0);
    lk.lock();
    ctx_map.erase(my_id);
    std::cerr << "returned ctx from thread-id:" << my_id << std::endl;
    lk.unlock();
}

void LinuxAlignedFileReader::deregister_all_threads()
{
    std::unique_lock<std::mutex> lk(ctx_mut);
    for (auto x = ctx_map.begin(); x != ctx_map.end(); x++)
    {
        io_context_t ctx = x.value();
        io_destroy(ctx);
        //  assert(ret == 0);
        //  lk.lock();
        //  ctx_map.erase(my_id);
        //  std::cerr << "returned ctx from thread-id:" << my_id << std::endl;
    }
    ctx_map.clear();
    //  lk.unlock();
}

void LinuxAlignedFileReader::open(const std::string &fname)
{
    coordinator.clear_ready();
    int flags = O_DIRECT | O_RDONLY | O_LARGEFILE;
    this->file_desc = ::open(fname.c_str(), flags);
    // error checks
    assert(this->file_desc != -1);
    std::cerr << "Opened file : " << fname << std::endl;
}

void LinuxAlignedFileReader::close()
{
    //  int64_t ret;

    // check to make sure file_desc is closed
    ::fcntl(this->file_desc, F_GETFD);
    //  assert(ret != -1);

    coordinator.clear_ready();
    ::close(this->file_desc);
    //  assert(ret != -1);
}

void LinuxAlignedFileReader::read(std::vector<AlignedRead> &read_reqs, io_context_t &ctx, bool async)
{
    if (async == true)
    {
        diskann::cout << "Async currently not supported in linux." << std::endl;
    }
    assert(this->file_desc != -1);
    auto* q=qshape::current();
    if(q){q->reader_requests+=read_reqs.size();for(const auto& r:read_reqs)q->reader_bytes+=r.len;}
    if(!q||(qshape::config().sharing=="off"&&qshape::config().retention=="none")){execute_io(ctx,this->file_desc,read_reqs);return;}
    std::vector<qshape::Coordinator::Ticket> tickets;
    std::vector<AlignedRead> owners;
    tickets.reserve(read_reqs.size());owners.reserve(read_reqs.size());
    try {
        const auto begin=qshape::now_ns();
        for(const auto& r:read_reqs){
            auto t=coordinator.acquire({r.offset,r.len},q->id,qshape::config().inflight_budget,qshape::config().sharing=="inflight");
            tickets.push_back(t);
            if(!t.req){++q->bypass;owners.push_back(r);}
            else if(t.owner)owners.emplace_back(r.offset,r.len,t.req->data);
            else {++q->shared_hits;q->shared_bytes+=r.len;if(t.req->owner==q->id)++q->same_query_hits;if(t.ready_hit){++q->ready_hits;q->ready_hit_bytes+=r.len;}}
        }
        q->lookup_ns+=qshape::now_ns()-begin;
        q->peak_shared_bytes=std::max(q->peak_shared_bytes,coordinator.peak());
        const auto io_start=qshape::config().breakdown?qshape::now_ns():0;
        execute_io(ctx,this->file_desc,owners);
        if(qshape::config().breakdown)q->owner_io_ns+=qshape::now_ns()-io_start;
    } catch(...) {
        auto error=std::current_exception();
        for(auto& t:tickets)if(t.owner)coordinator.publish(t.req,error);
        throw;
    }
    const auto publish_start=qshape::config().breakdown?qshape::now_ns():0;
    for(auto& t:tickets)if(t.owner)coordinator.publish(t.req);
    if(qshape::config().breakdown)q->publish_ns+=qshape::now_ns()-publish_start;
    const auto begin=qshape::now_ns();
    for(size_t i=0;i<tickets.size();++i)if(tickets[i].req)coordinator.consume(tickets[i].req,read_reqs[i].buf,tickets[i].owner);
    q->wait_copy_ns+=qshape::now_ns()-begin;
    q->peak_shared_bytes=std::max(q->peak_shared_bytes,coordinator.peak());
    q->peak_ready_bytes=std::max(q->peak_ready_bytes,coordinator.ready_peak());
    q->peak_inflight_bytes=std::max(q->peak_inflight_bytes,coordinator.inflight_peak());
}
