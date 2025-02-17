# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from abc import abstractmethod
from typing import Any, Callable, Iterable, Mapping, Optional, Type, Union

from pytorch_lightning.trainer.states import RunningStage
from pytorch_lightning.utilities.exceptions import MisconfigurationException
from torch.utils.data import Dataset, IterableDataset

from flash.core.data.properties import Properties
from flash.core.registry import FlashRegistry


class BaseDataset(Properties):

    DATASET_KEY = "dataset"

    transform_registry: Optional[FlashRegistry] = None

    @abstractmethod
    def load_data(self, data: Any) -> Union[Iterable, Mapping]:
        """The `load_data` hook should return either a Mapping or an Iterable.

        Override to add your dataset logic creation logic.
        """

    @abstractmethod
    def load_sample(self, data: Any) -> Any:
        """The `load_sample` hook contains the logic to load a single sample."""

    def __init__(self, running_stage: RunningStage) -> None:
        super().__init__()
        self.running_stage = running_stage

    def pass_args_to_load_data(
        self,
        *load_data_args: Any,
        **load_data_kwargs,
    ) -> "BaseDataset":
        self.data = self._load_data(*load_data_args, **load_data_kwargs)
        return self

    @property
    def running_stage(self) -> Optional[RunningStage]:
        return self._running_stage

    @running_stage.setter
    def running_stage(self, running_stage: RunningStage) -> None:
        self._running_stage = running_stage
        self.resolve_functions()

    def _resolve_functions(self, func_name: str, cls: Type["BaseDataset"]) -> None:
        from flash.core.data.data_pipeline import DataPipeline  # noqa F811

        function: Callable[[Any, Optional[Any]], Any] = getattr(
            self,
            DataPipeline._resolve_function_hierarchy(
                func_name,
                self,
                self.running_stage,
                cls,
            ),
        )
        setattr(self, f"_{func_name}", function)

    def _call_load_sample(self, sample: Any) -> Any:
        if self._load_sample:
            sample = self._load_sample(sample)
        return sample

    @classmethod
    def from_data(
        cls,
        *load_data_args,
        running_stage: Optional[RunningStage] = None,
        **dataset_kwargs: Any,
    ) -> "BaseDataset":
        if not running_stage:
            raise MisconfigurationException(
                "You should provide a running_stage to your dataset"
                " `from pytorch_lightning.trainer.states import RunningStage`."
            )
        flash_dataset = cls(**dataset_kwargs, running_stage=running_stage)
        flash_dataset.pass_args_to_load_data(*load_data_args)
        return flash_dataset

    def resolve_functions(self):
        raise NotImplementedError

    # Set to None as they are dymically resolved when the dataset is made stage aware
    # c.f running_stage is set in `__init__` function.
    _load_data = None
    _load_sample = None


class FlashDataset(Dataset, BaseDataset):
    """The ``FlashDataset`` is a ``BaseDataset`` and a :class:`~torch.utils.data.Dataset`.

    The `data` argument must be a ``Mapping`` (it must have a length).
    """

    def load_data(self, data: Any) -> Mapping:
        """By default, the `load_data` perform an identity operation.

        Override to add your own logic to load the data.
        """
        return data

    def load_sample(self, data: Any) -> Any:
        """By default, the `load_sample` perform an identity operation.

        Override to add your own logic to load a single sample.
        """
        return data

    def resolve_functions(self):
        self._resolve_functions("load_data", FlashDataset)
        self._resolve_functions("load_sample", FlashDataset)

    def __getitem__(self, index: int) -> Any:
        return self._call_load_sample(self.data[index])

    def __len__(self) -> int:
        return len(self.data)


class FlashIterableDataset(IterableDataset, BaseDataset):
    """The ``IterableAutoDataset`` is a ``BaseDataset`` and a :class:`~torch.utils.data.IterableDataset`.

    The `data` argument must be an ``Iterable``.
    """

    def load_data(self, data: Any) -> Iterable:
        """By default, the `load_data` perform an identity operation.

        Override to add your own logic to load the data.
        """
        return data

    def load_sample(self, data: Any) -> Any:
        """By default, the `load_sample` perform an identity operation.

        Override to add your own logic to load a single sample.
        """
        return data

    def resolve_functions(self):
        self._resolve_functions("load_data", FlashIterableDataset)
        self._resolve_functions("load_sample", FlashIterableDataset)

    def __iter__(self):
        self.data_iter = iter(self.data)
        return self

    def __next__(self) -> Any:
        return self._call_load_sample(next(self.data_iter))
