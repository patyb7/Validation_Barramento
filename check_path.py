import sys
import os

print("Conteúdo de sys.path:")
for p in sys.path:
    print(p)

print("\nDiretório de trabalho atual:")
print(os.getcwd())

try:
    import app.rules.phone.validator
    print("\nImportação de 'app.rules.phone.validator' foi bem-sucedida!")
except ImportError as e:
    print(f"\nImportação de 'app.rules.phone.validator' FALHOU: {e}")