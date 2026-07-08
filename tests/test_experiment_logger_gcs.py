"""
Unit tesztek az ExperimentLogger GCS-szinkronizációjához.
A google.cloud.storage.Client mockolva van — nincs élő GCS-hívás.
"""
import sys
import os
import importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class FakeBlob:
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def exists(self):
        return self.name in self.store

    def download_to_filename(self, path):
        with open(path, "wb") as f:
            f.write(self.store[self.name])

    def upload_from_filename(self, path):
        with open(path, "rb") as f:
            self.store[self.name] = f.read()


class FakeBucket:
    def __init__(self, store):
        self.store = store

    def blob(self, name):
        return FakeBlob(self.store, name)


class FakeStorageClient:
    _shared_store = {}

    def __init__(self, *a, **kw):
        pass

    def bucket(self, name):
        return FakeBucket(FakeStorageClient._shared_store)


def _install_fake_gcs(monkeypatch):
    import google.cloud.storage as real_storage
    FakeStorageClient._shared_store.clear()
    monkeypatch.setattr(real_storage, "Client", FakeStorageClient)


class TestGcsSync:
    def test_write_uploads_and_new_instance_downloads(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NEOMI_LOGS_GCS_BUCKET", "fake-bucket")
        _install_fake_gcs(monkeypatch)

        import experiment_logger
        importlib.reload(experiment_logger)  # re-read the env var into module-level GCS_BUCKET

        logdir_a = tmp_path / "instance_a"
        logger_a = experiment_logger.ExperimentLogger(logdir_a)
        logger_a.log({
            "run_id": "run-1", "experiment_id": "exp-001", "input_id": "in-1",
            "experiment_name": "Test", "optimization_strategy": "s",
            "started_at": "2026-07-08T00:00:00Z",
            "metrics": {"total_cost_usd": 0.05, "total_latency_seconds": 10, "total_tokens": 100},
            "evaluation": {"composite_score": 70.0, "dimension_scores": {}, "critic_issues_count": 0, "pareto_dominated": None},
            "errors": [],
        })

        # simulate a totally different Cloud Run instance: fresh, empty local dir
        logdir_b = tmp_path / "instance_b"
        logger_b = experiment_logger.ExperimentLogger(logdir_b)
        runs = logger_b.load_all_runs()

        assert len(runs) == 1
        assert runs[0]["run_id"] == "run-1"

        monkeypatch.delenv("NEOMI_LOGS_GCS_BUCKET", raising=False)
        importlib.reload(experiment_logger)

    def test_no_bucket_configured_is_pure_local_noop(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NEOMI_LOGS_GCS_BUCKET", raising=False)
        import experiment_logger
        importlib.reload(experiment_logger)

        logdir_a = tmp_path / "a"
        logger_a = experiment_logger.ExperimentLogger(logdir_a)
        logger_a.log({
            "run_id": "run-1", "experiment_id": "exp-001", "input_id": "in-1",
            "experiment_name": "Test", "optimization_strategy": "s",
            "started_at": "2026-07-08T00:00:00Z",
            "metrics": {"total_cost_usd": 0.05, "total_latency_seconds": 10, "total_tokens": 100},
            "evaluation": {"composite_score": 70.0, "dimension_scores": {}, "critic_issues_count": 0, "pareto_dominated": None},
            "errors": [],
        })

        # a different local dir does NOT see it — confirms no cross-instance magic without a bucket
        logdir_b = tmp_path / "b"
        logger_b = experiment_logger.ExperimentLogger(logdir_b)
        assert logger_b.load_all_runs() == []
