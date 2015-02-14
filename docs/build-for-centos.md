Build for CentOS
================

This document shows you how to build Aurora from the master branch on CentOS 6.5.
Once complete, you'll have built the scheduler, executors, runner, client, admin
client and observer.

In this document a CentOS 6.5 (x86_64) server with 8GB RAM and 20GB disk was
setup on Digital Ocean, though any hosting provider that allows you to perform
the steps outlined below should suffice.

These steps were tested against `0.7.1-SNAPSHOT`.

## Prepare the Environment

Before building Aurora, you first need to install the packages required to do
so.

SSH to the server, as `root` do the following:

```
yum -y update
yum groupinstall -y 'development tools'
yum install -y zlib-devel openssl-devel sqlite-devel bzip2-devel libcurl-devel cyrus-sasl-devel wget xz-libs

#   install python
#######################
cd ~
wget http://www.python.org/ftp/python/2.7.6/Python-2.7.6.tar.xz
xz -d Python-2.7.6.tar.xz
tar -xvf Python-2.7.6.tar
cd Python-2.7.6
./configure --prefix=/usr/local
make && make altinstall

#   Install Java
#######################
yum install -y java-1.7.0-openjdk-devel

#   Install Gradle
#######################
cd ~
wget https://services.gradle.org/distributions/gradle-2.2.1-all.zip
unzip gradle-2.2.1-all.zip

#  Update bash_profile
#######################
vi ~/.bash_profile

# put gradle and python on path
GRADLE_HOME=/root/gradle-2.2.1
PATH=/usr/local/bin:$PATH:$HOME/bin:$GRADLE_HOME/bin

source ~/.bash_profile
```

At this point you should have a slew of development related packages installed,
as well as Python 2.7, Java 7 and Gradle 2.2.1. Next, you'll build all of
the Aurora components.

## Build Aurora

Aurora consists of multiple components:

* scheduler
* executors (gc, thermos)
* runner (thermos)
* client
* admin client
* observer

The observer provides detailed stats for a job (on a process level). The
observer is not required but if you choose to deploy it, put it on each
mesos-slave.

Again, perform the following steps as `root`:

```
#   Get latest Aurora
#######################
cd ~
wget https://github.com/apache/incubator-aurora/archive/master.zip
unzip master.zip
cd incubator-aurora-master/

#   Build the clients
#######################
# See https://github.com/apache/incubator-aurora/blob/master/examples/vagrant/aurorabuild.sh
./pants binary src/main/python/apache/aurora/client/cli:aurora
./pants binary src/main/python/apache/aurora/admin:aurora_admin

#  Build the executors
#######################
# See https://github.com/apache/incubator-aurora/blob/master/examples/vagrant/aurorabuild.sh
# There's one problem, the executors require mesos.native. When first trying to build
# these I got an error "python pants Cannot satisfy requirements [PythonRequirement(mesos.native==0.21.1)]".
# I googled for "python pants Cannot satisfy requirements" and found this http://mail-archives.apache.org/mod_mbox/aurora-dev/201410.mbox/%3CCAHD-6f8PkS84Fdp_Y3gnzZtk=TKgmV=02KH4E+5akM6OzdR0EQ@mail.gmail.com%3E
# We need to get a mesos.native egg file and put it into a directory called third_party
mkdir third_party
MESOS_VERSION=0.21.1
wget -c https://svn.apache.org/repos/asf/incubator/aurora/3rdparty/centos/6/python/mesos.native-${MESOS_VERSION}-py2.7-linux-x86_64.egg
mv mesos.native*.egg third_party/
./pants binary src/main/python/apache/aurora/executor/bin:gc_executor
./pants binary src/main/python/apache/aurora/executor/bin:thermos_executor
./pants binary src/main/python/apache/thermos/bin:thermos_runner

# package runner within executor
python2.7 << EOF
import contextlib
import zipfile
with contextlib.closing(zipfile.ZipFile('dist/thermos_executor.pex', 'a')) as zf:
  zf.writestr('apache/aurora/executor/resources/__init__.py', '')
  zf.write('dist/thermos_runner.pex', 'apache/aurora/executor/resources/thermos_runner.pex')
EOF

#   Build the observer
#######################
./pants binary src/main/python/apache/thermos/observer/bin:thermos_observer

#   Build the scheduler
#######################
gradle wrapper
./gradlew distTar
```

At this point you should have a bunch of stuff under the `dist` directory:

```
[root@aurora incubator-aurora-0.7.1-master]# ll dist/
total 62660
-rwxr-xr-x 1 root root  2261321 Feb 13 06:33 aurora_admin.pex
-rwxr-xr-x 1 root root  2310121 Feb 13 06:33 aurora.pex
drwxr-xr-x 3 root root     4096 Feb 13 06:43 classes
drwxr-xr-x 2 root root     4096 Feb 13 06:43 dependency-cache
drwxr-xr-x 2 root root     4096 Feb 13 06:43 distributions
-rwxr-xr-x 1 root root 27827250 Feb 13 06:31 gc_executor.pex
drwxr-xr-x 2 root root     4096 Feb 13 06:43 libs
drwxr-xr-x 3 root root     4096 Feb 13 06:43 resources
drwxr-xr-x 2 root root     4096 Feb 13 06:43 scripts
-rwxr-xr-x 1 root root 29577947 Feb 13 06:33 thermos_executor.pex
-rwxr-xr-x 1 root root  1559836 Feb 13 06:33 thermos_observer.pex
-rwxr-xr-x 1 root root   586063 Feb 13 06:32 thermos_runner.pex
drwxr-xr-x 4 root root     4096 Feb 13 06:43 tmp
```

You'll want `dist/*.pex` and `dist/distributions/aurora-scheduler-*.tar`.

## Run Aurora

You can look at the upstart conf files to start the [scheduler](https://github.com/apache/incubator-aurora/blob/master/examples/vagrant/upstart/aurora-scheduler.conf) and [observer](https://github.com/apache/incubator-aurora/blob/master/examples/vagrant/upstart/aurora-thermos-observer.conf).
