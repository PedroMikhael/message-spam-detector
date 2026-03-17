
# Uso:
#   python autorizar_gmail.py --conta uece      → gera token_uece.json
#   python autorizar_gmail.py --conta pessoal   → gera token_pessoal.json
#   python autorizar_gmail.py                   → menu interativo

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CONTA_MAP = {
    "uece": "token_uece.json",
    "pessoal": "token_pessoal.json",
}


def authorize(token_file):
    print(f"Iniciando fluxo de autorização para: {token_file}")
    print("O navegador vai abrir. Faça login com a conta desejada.\n")

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=8080, prompt='consent')

    with open(token_file, "w") as f:
        f.write(creds.to_json())

    print(f"\n Autorização concluída! Token salvo em '{token_file}'.")


def main():
    # Verificar argumento --conta
    conta = None
    if "--conta" in sys.argv:
        idx = sys.argv.index("--conta")
        if idx + 1 < len(sys.argv):
            conta = sys.argv[idx + 1].lower()

    if conta:
        if conta not in CONTA_MAP:
            print(f"Conta '{conta}' não reconhecida. Use: {', '.join(CONTA_MAP.keys())}")
            sys.exit(1)
        token_file = CONTA_MAP[conta]
    else:
        
        print("Qual conta deseja autorizar?\n")
        for i, (nome, arquivo) in enumerate(CONTA_MAP.items(), 1):
            exists = "(token existe)" if os.path.exists(arquivo) else "(sem token)"
            print(f"  {i}. {nome.upper()} → {arquivo} {exists}")

        print()
        escolha = input("Digite o número (ou 'uece'/'pessoal'): ").strip().lower()

        if escolha in CONTA_MAP:
            token_file = CONTA_MAP[escolha]
        elif escolha.isdigit():
            keys = list(CONTA_MAP.keys())
            idx = int(escolha) - 1
            if 0 <= idx < len(keys):
                token_file = CONTA_MAP[keys[idx]]
            else:
                print("Opção inválida.")
                sys.exit(1)
        else:
            print("Opção inválida.")
            sys.exit(1)

    authorize(token_file)


if __name__ == "__main__":
    main()
