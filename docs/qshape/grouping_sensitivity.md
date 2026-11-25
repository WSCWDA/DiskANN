# P3.1-D2

Run from repository root. Default 45 searches: G=64,128,256,512, P=512, three retention policies, sharing on, plus original G256/P512 controls, three repeats. Optional POOL_SIZES='512 1024 2048' adds pool sweep at G256. Validator accepts matching --group-sizes and --pool-sizes. All diagnostics off; group IDs are logical, not concurrency measurements. Cross-case result hashes and logical counts checked by validator. Run `bash tests/qshape/test_grouping_sensitivity.sh` for mock runner test. No C++ changes.
