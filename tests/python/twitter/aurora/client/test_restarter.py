from twitter.aurora.client.restarter import Restarter
from twitter.aurora.client.shard_watcher import ShardWatcher
from twitter.aurora.client.updater_util import UpdaterConfig
from twitter.aurora.common import AuroraJobKey

from gen.twitter.aurora.AuroraSchedulerManager import Client as scheduler_client
from gen.twitter.aurora.ttypes import *

from mox import IgnoreArg, MoxTestBase

from .helper import FakeSchedulerProxy


SESSION_KEY = 'test_session'
CLUSTER='smfd'
JOB = AuroraJobKey(CLUSTER, 'johndoe', 'test', 'test_job')
HEALTH_CHECK_INTERVAL_SECONDS = 5
UPDATER_CONFIG = UpdaterConfig(
    2, # batch_size
    23, # restart_threshold
    45, #watch_secs
    0, # max_per_shard_failures
    0 # max_total_failures
)


class TestRestarter(MoxTestBase):

  def setUp(self):
    super(TestRestarter, self).setUp()

    self.mock_scheduler = self.mox.CreateMock(scheduler_client)
    self.mock_shard_watcher = self.mox.CreateMock(ShardWatcher)

    self.restarter = Restarter(
        JOB, UPDATER_CONFIG, HEALTH_CHECK_INTERVAL_SECONDS,
        FakeSchedulerProxy(CLUSTER, self.mock_scheduler, SESSION_KEY), self.mock_shard_watcher)

  def mock_restart_shards(self, shards):
    response = Response(responseCode=ResponseCode.OK, message='test')

    self.mock_scheduler.restartShards(JOB.to_thrift(), shards, SESSION_KEY).AndReturn(response)
    self.mock_shard_watcher.watch(shards).AndReturn([])

  def test_restart_one_iteration(self):
    self.mock_restart_shards([0, 1])

    self.mox.ReplayAll()

    self.restarter.restart([0, 1])

  def mock_three_iterations(self):
    self.mock_restart_shards([0, 1])
    self.mock_restart_shards([3, 4])
    self.mock_restart_shards([5])

  def test_rolling_restart(self):
    self.mock_three_iterations()

    self.mox.ReplayAll()

    self.restarter.restart([0, 1, 3, 4, 5])

  def mock_status_active_tasks(self, shardids):
    tasks = []
    for i in shardids:
      tasks.append(ScheduledTask(
          status=ScheduleStatus.RUNNING,
          assignedTask=AssignedTask(task=TaskConfig(shardId=i))
      ))
    response = ScheduleStatusResponse(responseCode=ResponseCode.OK, message='test', tasks=tasks)

    self.mock_scheduler.getTasksStatus(IgnoreArg()).AndReturn(response)

  def test_restart_all_shards(self):
    self.mock_status_active_tasks([0, 1, 3, 4, 5])
    self.mock_three_iterations()

    self.mox.ReplayAll()

    self.restarter.restart(None)

  def mock_status_no_active_task(self):
    response = ScheduleStatusResponse(responseCode=ResponseCode.INVALID_REQUEST, message='test', tasks=None)
    self.mock_scheduler.getTasksStatus(IgnoreArg()).AndReturn(response)

  def test_restart_no_shard_active(self):
    self.mock_status_no_active_task()

    self.mox.ReplayAll()

    self.restarter.restart(None)

  def mock_restart_fails(self):
    response = Response(responseCode=ResponseCode.ERROR, message='test error')

    self.mock_scheduler.restartShards(JOB.to_thrift(), IgnoreArg(), SESSION_KEY).AndReturn(response)

  def test_restart_shard_fails(self):
    self.mock_status_active_tasks([0, 1])
    self.mock_restart_fails()

    self.mox.ReplayAll()

    assert self.restarter.restart(None).responseCode == ResponseCode.ERROR

  def mock_restart_watch_fails(self, shards):
    response = Response(responseCode=ResponseCode.OK, message='test')

    self.mock_scheduler.restartShards(JOB.to_thrift(), shards, SESSION_KEY).AndReturn(response)
    self.mock_shard_watcher.watch(shards).AndReturn(shards)

  def test_restart_shards_watch_fails(self):
    shards = [0, 1]
    self.mock_status_active_tasks(shards)
    self.mock_restart_watch_fails(shards)

    self.mox.ReplayAll()

    self.restarter.restart(None)