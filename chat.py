import openai, subprocess, re
from argparse import ArgumentParser


openai.api_key = '...'

SYSTEM_MSG = """Ada is a helpful chatbot with access to various
APIs. It may or may not use the APIs depending on the user query. She is
extremely intelligent. She tries her best to do any task or answer
any question asked by the user.

Ada's API calls MUST follow this format:
 
ACT
API_NAME
API_QUERY
TCA

Ada MUST NOT deviate from the format! There will be ATMOST ONE API call per
response. She will not call more than once.

---

Python API call format:

ACT
PYTHON
```python
< code here >
```
TCA

Ada must follow this Python API call format exactly! Include Python code
between triple backticks ``` and the `python` indicator!

Example:

ACT
PYTHON
```python
import math


x = math.sin(2 * math.pi)
assert x == 0.
print(x)
```
TCA

---

Calculator API format:

ACT
CALCULATE
operation
TCA

Example:

ACT
CALCULATE
(2 + 5) * 10 / 3
TCA

---"""


def parse(response):
  match = re.search(r'ACT[\n\s]*(.*?)[\n\s]*TCA', response, re.DOTALL)
  if not match:
    return None
  call = match.group(1)
  action, query = call.split("\n", 1)
  return action, query


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
  return (result.stdout + result.stderr).rstrip('\n')


def run_calculation(query):
  try:
    return eval(query)
  except Exception as e:
    return f"Error during calculation: {str(e)}"


def complete(model, messages):
  return openai.ChatCompletion.create(
    model=model,
    messages=messages
  ).choices[0].message.content


def main(model):
  actions = {'PYTHON': run_python_code, 'CALCULATE': run_calculation} 
  messages = [{'role': 'system', 'content': SYSTEM_MSG}]
  while True:
    user = input('\n\nUSER: ')
    if user.strip() == '\end':
      print('\nCHAT FINISHED')
      break
    messages.append({'role': 'user', 'content': user})

    while True:
      print('\nADA: ', end='')
      response = complete(model, messages)
      print(response, end='')
      messages.append({'role': 'assistant', 'content': response})
      call = parse(response)

      if call is None:
        break

      action, query = call
      if action in actions:
        result = 'RESULT FROM API CALL:\n\n' + str(actions[action](query)) + '\n'
      else:
        result = 'Invalid API call!\n'
      
      print(f'\n\n{result}', end='')
      messages.append({'role': 'user', 'content': result})


if __name__ == '__main__':
  parser = ArgumentParser()
  parser.add_argument('--model', default='gpt-4', type=str)
  args = parser.parse_args()
  main(args.model)
