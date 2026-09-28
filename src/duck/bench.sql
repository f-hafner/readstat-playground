INSTALL read_stat FROM community;
LOAD read_stat;
.timer on
FROM read_stat("data/test_small.sav"); 
-- NULLs are correct; categorical labels not converted
.quit

