import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from src.core.llm import LLM
llm = LLM()
prompt = (
    "You are a Chinese rental contract expert. "
    "Based on: monthly rent 3500, deposit 7000, payment: 2 deposit 3 rent. "
    "Return JSON: {\"summary\": \"brief\", \"key_risks\": [\"risk1\"], \"negotiation_tips\": [\"tip1\"]}"
)
start = time.time()
result = llm.generate(prompt, system="Return only JSON.", timeout=10)
elapsed = time.time() - start
print(f'Elapsed: {elapsed:.1f}s')
print(f'Result: {repr(result[:200])}')
print('DONE')
