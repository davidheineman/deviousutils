Deviously useful utilities

```sh
pip install deviousutils
```

### HF Utils

```python
from deviousutils import hf

hf.push_parquet_to_hf(file_path, hf_dataset_name)
hf.pull_parquet_from_hf(repo_id, split_name)
```