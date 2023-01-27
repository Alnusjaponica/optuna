import warnings

from packaging import version

import optuna
from optuna.storages._cached_storage import _CachedStorage
from optuna.storages._rdb.storage import RDBStorage


# Define key names of `Trial.system_attrs`.
_EPOCH_KEY = "ddp_pl:epoch"
_PRUNED_KEY = "ddp_pl:pruned"
_MESSAGE_KEY = "ddp_pl:message"
_INTERMEDIATE_VALUE = "ddp_pl:intermediate_value"

with optuna._imports.try_import() as _imports:
    import pytorch_lightning as pl
    from pytorch_lightning import LightningModule
    from pytorch_lightning import Trainer
    from pytorch_lightning.callbacks import Callback

if not _imports.is_successful():
    Callback = object  # type: ignore  # NOQA
    LightningModule = object  # type: ignore  # NOQA
    Trainer = object  # type: ignore  # NOQA


class PyTorchLightningPruningCallback(Callback):
    """PyTorch Lightning callback to prune unpromising trials.

    See `the example <https://github.com/optuna/optuna-examples/blob/
    main/pytorch/pytorch_lightning_simple.py>`__
    if you want to add a pruning callback which observes accuracy.

    Args:
        trial:
            A :class:`~optuna.trial.Trial` corresponding to the current evaluation of the
            objective function.
        monitor:
            An evaluation metric for pruning, e.g., ``val_loss`` or
            ``val_acc``. The metrics are obtained from the returned dictionaries from e.g.
            ``pytorch_lightning.LightningModule.training_step`` or
            ``pytorch_lightning.LightningModule.validation_epoch_end`` and the names thus depend on
            how this dictionary is formatted.

    .. note::
        For the distributed data parallel training, the version of PyTorchLightning needs to be
        higher than or equal to v1.5.0. In addition, :class:`~optuna.study.Study` should be
        instantiated with RDB storage.
    """

    def __init__(self, trial: optuna.trial.Trial, monitor: str) -> None:
        _imports.check()
        super().__init__()

        self._trial = trial
        self.monitor = monitor
        self.is_ddp_backend = False
        self._trial.storage.set_trial_system_attr(
            self._trial._trial_id,
            _INTERMEDIATE_VALUE,
            dict(),
        )

    def on_fit_start(self, trainer: Trainer, pl_module: "pl.LightningModule") -> None:
        self.is_ddp_backend = trainer._accelerator_connector.is_distributed
        if self.is_ddp_backend:
            if version.parse(pl.__version__) < version.parse("1.5.0"):  # type: ignore
                raise ValueError("PyTorch Lightning>=1.5.0 is required in DDP.")
            # If it were not for this block, fitting is started even if unsupported storage
            # is used. Note that the ValueError is transformed into ProcessRaisedException inside
            # torch.
            if not (
                isinstance(self._trial.study._storage, _CachedStorage)
                and isinstance(self._trial.study._storage._backend, RDBStorage)
            ):
                raise ValueError(
                    "optuna.integration.PyTorchLightningPruningCallback"
                    " supports only optuna.storages.RDBStorage in DDP."
                )

    def on_validation_end(self, trainer: Trainer, pl_module: LightningModule) -> None:

        # When the trainer calls `on_validation_end` for sanity check,
        # do not call `trial.report` to avoid calling `trial.report` multiple times
        # at epoch 0. The related page is
        # https://github.com/PyTorchLightning/pytorch-lightning/issues/1391.
        if trainer.sanity_checking:
            return

        current_score = trainer.callback_metrics.get(self.monitor)
        if current_score is None:
            message = (
                "The metric '{}' is not in the evaluation logs for pruning. "
                "Please make sure you set the correct metric name.".format(self.monitor)
            )
            warnings.warn(message)
            return

        epoch = pl_module.current_epoch
        should_stop = False
        if trainer.is_global_zero:
            self._trial.report(current_score.item(), step=epoch)
            should_stop = self._trial.should_prune()
            # update intermediate value in storage
            _trial_id = self._trial._trial_id
            _study = self._trial.study
            _trial_system_attrs = _study._storage.get_trial_system_attrs(_trial_id)
            intermediate_values = _trial_system_attrs.get(_INTERMEDIATE_VALUE)
            if isinstance(intermediate_values, dict):
                intermediate_values[epoch] = current_score.item()
            self._trial.storage.set_trial_system_attr(
                self._trial._trial_id, _INTERMEDIATE_VALUE, intermediate_values
            )

        # stop every ddp process if any world process decides to stop
        should_stop = trainer.strategy.reduce_boolean_decision(should_stop, all=False)
        trainer.should_stop = trainer.should_stop or should_stop
        if not should_stop:
            return
        self.stopped_epoch = epoch

        if not self.is_ddp_backend:
            message = "Trial was pruned at epoch {}.".format(epoch)
            raise optuna.TrialPruned(message)
        else:
            # update system_attr from global zero process
            if trainer.is_global_zero:
                self._trial.storage.set_trial_system_attr(self._trial._trial_id, _EPOCH_KEY, epoch)
                self._trial.storage.set_trial_system_attr(self._trial._trial_id, _PRUNED_KEY, True)
                self._trial.storage.set_trial_system_attr(
                    self._trial._trial_id,
                    _MESSAGE_KEY,
                    "Trial was pruned at epoch {}.".format(epoch),
                )

    def check_pruned(self) -> None:
        """Raise :class:`optuna.TrialPruned` manually if pruned."""

        _trial_id = self._trial._trial_id
        _study = self._trial.study
        _trial_system_attrs = _study._storage._backend.get_trial_system_attrs(  # type: ignore[attr-defined] # NOQA: E501
            _trial_id
        )
        is_pruned = _trial_system_attrs.get(_PRUNED_KEY)
        intermediate_values = _trial_system_attrs.get(_INTERMEDIATE_VALUE)
        for epoch, score in intermediate_values.items():
            self._trial.report(score, step=int(epoch))
        if is_pruned:
            message = _trial_system_attrs.get(_MESSAGE_KEY)
            raise optuna.TrialPruned(message)
