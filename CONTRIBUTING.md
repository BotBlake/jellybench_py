# Contributors Guide

Thank you for wanting to contribute....
We have a GitHub Project to track Progress...

## Developer Documentation

jellybench_py offers a few development specific features. Some of them are not documented in the ReadMe and dont show up in the help menue.
That is to prevent End-Users from abusing them to manipulate the uploaded data.

However the commands should speed up development.
Therefore they are documented here. Note that they all will only take effect when the `--debug` Flag is set. 

|Argument|Parameters|Description|Status|
|---|---|---|
|`--ignorehash`|None|Ignores Checksum missmatch|Active|
|`--server`|`{Path/to/tests.json}`|Provide local tests instead of a Server URL|Currently unavailable|
|`--override-platform`|`{Platform Name}`|
