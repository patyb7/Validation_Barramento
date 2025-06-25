import asyncio
import sys
import os
import logging

# Configuração de logging para o script de teste
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Adiciona o diretório raiz do projeto (Validation_Barramento) ao sys.path para permitir importações absolutas
script_dir = os.path.dirname(__file__)
# Suba dois níveis para chegar em 'Validation_Barramento'
project_root_to_add = os.path.abspath(os.path.join(script_dir, '..', '..'))
if project_root_to_add not in sys.path:
    sys.path.insert(0, project_root_to_add)
    logger.info(f"Adicionado '{project_root_to_add}' ao sys.path.")

try:
    # IMPORTANTE: Importa a classe PhoneValidator diretamente do seu módulo de aplicação
    # Isso garante que você esteja testando a implementação real e suas constantes.
    from app.rules.phone.validator import PhoneValidator

    # As constantes RNT_PHNXXX agora são atributos da classe PhoneValidator
    # e serão acessadas via PhoneValidator.RNT_PHNXXX
    # Não é necessário redefiní-las globalmente aqui.

except ImportError as e:
    logger.error(f"Erro ao importar módulos. Certifique-se de que o diretório raiz do projeto ('Validation_Barramento') está no PYTHONPATH e que 'phonenumbers' está instalado. Erro: {e}")
    sys.exit(1)
except Exception as e:
    logger.critical(f"Erro inesperado durante a inicialização do PhoneValidator no script de teste: {e}", exc_info=True)
    sys.exit(1)

async def run_tests():
    """
    Executa os casos de teste para o PhoneValidator.
    """
    validator = PhoneValidator() # Instancia o validador real

    test_cases = [
        # Casos de sucesso no Brasil
        {"number": "11987654321", "hint": "BR", "expected_valid": True, "description": "Celular BR válido (sem +55)"},
        {"number": "+5511987654321", "hint": "BR", "expected_valid": True, "description": "Celular BR válido (com +55)"},
        {"number": "2130001000", "hint": "BR", "expected_valid": True, "description": "Fixo BR válido (sem +55)"},
        {"number": "(11) 98765-4321", "hint": "BR", "expected_valid": True, "description": "Celular BR formatado"},
        {"number": "1133333333", "hint": "BR", "expected_valid": True, "description": "Fixo BR formatado"},
        {"number": "011987654321", "hint": "BR", "expected_valid": True, "description": "Celular BR com zero de operadora"},
        
        # Números de emergência BR
        {"number": "190", "hint": "BR", "expected_valid": True, "description": "Número de emergência BR (190)"},
        {"number": "192", "hint": None, "expected_valid": True, "description": "Número de emergência BR (192, sem hint)"},

        # Casos inválidos no Brasil (phonenumbers e fallback)
        {"number": "11123", "hint": "BR", "expected_valid": False, "description": "Celular BR muito curto"},
        {"number": "119999999999999", "hint": "BR", "expected_valid": False, "description": "Celular BR muito longo"},
        {"number": "1199999999123", "hint": "BR", "expected_valid": False, "description": "Celular BR inválido por phonenumbers (comprimento)"},
        # Agora as regras esperadas referenciam os atributos da CLASSE PhoneValidator
        {"number": "0000000000", "hint": "BR", "expected_valid": False, "description": "Número sequencial/repetido (todos zeros)", "expected_rule": PhoneValidator.RNT_PHN013},
        {"number": "12345678901", "hint": "BR", "expected_valid": False, "description": "Número sequencial crescente", "expected_rule": PhoneValidator.RNT_PHN013},
        {"number": "09876543210", "hint": "BR", "expected_valid": False, "description": "Número sequencial decrescente", "expected_rule": PhoneValidator.RNT_PHN013},
        {"number": "1000000000", "hint": "BR", "expected_valid": False, "description": "DDD inválido (10)", "expected_rule": PhoneValidator.RNT_PHN011}, 
        {"number": "1187654321", "hint": "BR", "expected_valid": False, "description": "Celular BR inválido (não começa com 9)", "expected_rule": PhoneValidator.RNT_PHN012},

        # Casos internacionais
        {"number": "+12125551234", "hint": "US", "expected_valid": True, "description": "EUA válido (com +1)"},
        {"number": "2125551234", "hint": "US", "expected_valid": True, "description": "EUA válido (sem +1, com hint)"},
        {"number": "+442079460000", "hint": "GB", "expected_valid": True, "description": "UK válido"},
        {"number": "+34911234567", "hint": "ES", "expected_valid": True, "description": "Espanha válido"},
        {"number": "004917612345678", "hint": "DE", "expected_valid": True, "description": "Alemanha válido (com 00 internacional)"},
        
        # Casos inválidos internacionais
        {"number": "+111111111111111111", "hint": "US", "expected_valid": False, "description": "EUA muito longo"},
        {"number": "+123", "hint": "US", "expected_valid": False, "description": "EUA muito curto"},
        {"number": "abc", "hint": "BR", "expected_valid": False, "description": "Input não numérico"},
        {"number": "", "hint": "BR", "expected_valid": False, "description": "Input vazio"},
        {"number": "   ", "hint": "BR", "expected_valid": False, "description": "Input só com espaços"},
        {"number": None, "hint": "BR", "expected_valid": False, "description": "Input None"},
        {"number": 123456789, "hint": "BR", "expected_valid": False, "description": "Input não string (int)"},
    ]

    print("\n--- Iniciando testes do PhoneValidator ---\n")
    
    for i, case in enumerate(test_cases):
        phone_number = case["number"]
        country_hint = case["hint"]
        expected_valid = case["expected_valid"]
        description = case["description"]
        expected_rule = case.get("expected_rule")

        print(f"--- Teste {i+1}: {description} ---")
        print(f"  Número: '{phone_number}' (Hint: '{country_hint}')")
        
        result = await validator.validate(phone_number, country_hint=country_hint)
        
        print(f"  Resultado Validador: is_valid={result['is_valid']}, normalizado='{result['dado_normalizado']}'")
        print(f"  Mensagem: {result['mensagem']}")
        print(f"  Origem: {result['origem_validacao']}")
        print(f"  Regra Aplicada: Código={result['business_rule_applied']['code']}, Nome='{result['business_rule_applied']['name']}'")
        # Opcional: imprimir detalhes adicionais se existirem
        if result['details']:
            print(f"  Detalhes: {result['details']}")

        # Verificação do resultado
        test_passed = (result['is_valid'] == expected_valid)
        
        # Verificação da regra de negócio esperada, se fornecida
        if expected_rule:
            if result['business_rule_applied']['code'] == expected_rule:
                print(f"  -> Regra de Negócio Esperada '{expected_rule}' aplicada. ✅")
            else:
                print(f"  -> Regra de Negócio Esperada '{expected_rule}' NÃO aplicada. Aplicada: '{result['business_rule_applied']['code']}'. ❌")
                test_passed = False # Falha o teste se a regra esperada não for aplicada

        if test_passed:
            print("  STATUS: PASSED ✅\n")
        else:
            print("  STATUS: FAILED ❌\n")

    print("--- Testes do PhoneValidator concluídos ---")

if __name__ == "__main__":
    asyncio.run(run_tests())
