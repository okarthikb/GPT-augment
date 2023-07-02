import os, re, subprocess, openai, cohere
from argparse import ArgumentParser


openai.api_key = os.getenv('OPENAI_API_KEY')
co = cohere.Client(os.getenv('COHERE_API_KEY'))

SYSTEM_MSG = """Ada is a helpful chatbot with access to various
APIs. It may or may not use the APIs depending on the user query. She is
extremely intelligent. She tries her best to do any task or answer
any question asked by the user.

Ada's API calls MUST follow this format:

ACT
API_NAME
API_QUERY
TCA

where API_QUERY is the input to the API function and can be multiple lines
(each line a seperate argument).

Ada MUST NOT deviate from the format!

There SHOULD be ATMOST ONE API call per response, i.e., there should be
atmost one ACT-TCA block per response. If the response contains the API call
(i.e., the ACT-TCA block), the result of the API call will be printed
subsequently.

The response parser will only consider the FIRST (if it exists) ACT-TCA block.

In the response _after_ the API call result, Ada may or may not choose to call
an API again.

–––

Python API call format:

ACT
PYTHON
```python
< code here >
```
TCA

Ada must follow this Python API call format exactly! Include Python code
between triple backticks ``` and the `python` indicator!

The output - not the return value - of the code will be included in the result
from the API call. So _always_ print the result of the code.

Example:

This is bad. It will not print the result of the code, it only returns the
result.

ACT
PYTHON
```python
import math


x = math.sin(2 * math.pi)
assert x == 0.
x
```
TCA

This is good. It will print the result of the code.

ACT
PYTHON
```python
import math


x = math.sin(2 * math.pi)
assert x == 0.
print(x)
```
TCA

ALWAYS PRINT RESULTS!

–––

Calculator API format:

ACT
CALCULATE
expression
TCA

Example:

ACT
CALCULATE
(2 + 5) * 10 / 3
TCA

–––

Cohere rerank retrieval API format:

ACT
RERANK
query
max_chunks_per_doc
file_name
TCA

Explanation:

Rerank is used for retrieving relevant portion of a text file. The text file
contains a number of lines, each line is a document. The query is used to
rerank the documents and return the best one. The best one is printed as the
result from the API call.

Parameters:

query: the query to rerank the documents with and return the best one

max_chunks_per_doc: if your document exceeds 512 tokens, this will determine
the maximum number of chunks a document can be split into. For example, if
your document is 6000 tokens, with the default of 10, the document will be
split into 10 chunks each of 512 tokens and the last 880 tokens will be
disregarded.

file_name: The text file that contains a document per line.

Example:

ACT
RERANK
What is the capital of France?
10
countries.txt
TCA

–––"""


def parse(response):
  match = re.search(r'ACT[\n\s]*(.*?)[\n\s]*TCA', response, re.DOTALL)
  if not match:
    return None
  call = match.group(1)
  try:
    action, query = call.split("\n", 1)
    return action, query
  except Exception as e:
    return "ERROR", f'```\n{str(e)}\n```'


def run_python_code(query):
  code_match = re.search(r'```python[\n\s]*(.*?)[\n\s]*```', query, re.DOTALL)
  if not code_match:
    return 'Problem with Python API call format!'
  code = code_match.group(1)
  result = subprocess.run(
    ['python3', '-c', code],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
  )
  result = (result.stdout + result.stderr).rstrip('\n')
  return f'```\n{result}\n```' if result else '``` ```'


def run_eval(query):
  try:
    return '```\n' + eval(query) + '\n```'
  except Exception as e:
    return f'```\nError using eval: {str(e)}\n```'


def run_rerank(query):
  try:
    query, max_chunks_per_doc, file_name = query.split("\n")
    docs = open(file_name, 'r').readlines()
    rerank_hits = co.rerank(
      model="rerank-english-v2.0",
      query=query,
      documents=docs,
      max_chunks_per_doc=int(max_chunks_per_doc),
      top_n=1
    )
    hit = rerank_hits[0]
    return f'```\n– document start –\n{docs[hit.index]}\n– document end –\n```'
  except Exception as e:
    return f'```\nError using rerank: {str(e)}\n```'


def complete(model, messages):
  return openai.ChatCompletion.create(
    model=model,
    messages=messages
  ).choices[0].message.content


def main(model, max_retries):
  actions = {
    'PYTHON': run_python_code,
    'CALCULATE': run_eval,
    'RERANK': run_rerank,
    'ERROR': lambda e: f'Invalid API call format!\n\n' + e
  }
  messages = [{'role': 'system', 'content': SYSTEM_MSG}]
  while True:
    user = input('\nUser: ')
    if user == '\end':
      print('\nChat finished.\n')
      break
    messages.append({'role': 'user', 'content': user})
    for _ in range(max_retries):
      print('\nAda: ', end='')
      response = complete(model, messages)
      if response.startswith('ACT'):
        print('\n\n' + response)
      else:
        print(response)
      messages.append({'role': 'assistant', 'content': response})
      call = parse(response)
      if call is None:
        break
      action, query = call
      if action in actions:
        proceed = input('\nProceed? (y/n): ')
        if proceed == 'n':
          break
        result = '\nAPI call result:\n\n' + actions[action](query)
      else:
        result = "\nAPI doesn't exist! Use a different one."
      print(result)
      messages.append({'role': 'user', 'content': result})


if __name__ == '__main__':
  parser = ArgumentParser()
  parser.add_argument('--model', default='gpt-4-0613', type=str)
  parser.add_argument('--max_retries', default=6, type=int)
  args = parser.parse_args()
  main(args.model, args.max_retries)
