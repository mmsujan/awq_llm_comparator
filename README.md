## Installation

 - Clone "awq_llm_comparator"
 - Open Anaconda prompt ( Recommended)
 - cd to "awq_llm_comparator" directory
 
Run following command to create conda environment
 
```
conda env create -f environment.yaml
conda activate awq_llm
pip install -r requirements.txt

```


## Run Test
 - Collect int4_awq_llm_2 models from [int4_awq_llm_2]() 
 - Unzip " models" directory and put it inside "awq_llm_comparator"
 - From conda or command prompt, cd path to "awq_llm_comparator" directory  
 
 Sample Run: 
 ```
 python compare.py --model_type=llama-2-7b-chat
 ```
 - You must set model type. Model types are : llama-2-7b-chat, mistral-7b-chat or phi-2
 
 - You can set different threshold values as per requirement. For an example:
 ```
 python compare.py --model_type=llama-2-7b-chat --threshold=5
 ```
 - Command line argument options:
 
```
usage: compare.py [-h] [--threshold THRESHOLD] [--compare_mode COMPARE_MODE] [--platform PLATFORM] [--verbosity] --model_type {llama-2-7b-chat, mistral-7b-chat, phi-2} 

optional arguments:
  -h, --help            show this help message and exit

text comparator params:
  --threshold THRESHOLD
                        Maximum number of difference between generated and golden text.
  --compare_mode COMPARE_MODE
                        Compare mode : Character, Word or Line
  --verbosity           Print error details
  --model_type          Which model to run (llama-2-7b-chat, mistral-7b-chat or phi-2).

```
