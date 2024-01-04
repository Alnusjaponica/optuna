.. module:: optuna.cli

optuna.cli
==========

The :mod:`~optuna.cli` module implements Optuna's command-line functionality.

For detail, please see the result of

.. code-block:: console

    $ optuna --help

.. seealso::
    The :ref:`cli` tutorial provides use-cases with examples.

.. argparse::
    :module: optuna.cli
    :func: _CreateStudy
    :prog: optuna create-study

.. argparse::
    :module: optuna.cli
    :func: _DeleteStudy
    :prog: optuna delete-study

.. argparse::
    :module: optuna.cli
    :func: _StudySetUserAttribute
    :prog: optuna study set-user-attr

.. argparse::
    :module: optuna.cli
    :func: _StudyNames
    :prog: optuna study-names

.. argparse::
    :module: optuna.cli
    :func: _Studies
    :prog: optuna studies

.. argparse::
    :module: optuna.cli
    :func: _Trials
    :prog: optuna trials

.. argparse::
    :module: optuna.cli
    :func: _BestTrial
    :prog: optuna best-trial

.. argparse::
    :module: optuna.cli
    :func: _StudyOptimize
    :prog: optuna study optimize

.. argparse::
    :module: optuna.cli
    :func: _StorageUpgrade
    :prog: optuna storage upgrade

.. argparse::
    :module: optuna.cli
    :func: _Ask
    :prog: optuna ask

.. argparse::
    :module: optuna.cli
    :func: _Tell
    :prog: optuna tell
