# TAPRC-2026

Projeto acadêmico da disciplina — Azure Functions com **Timer Trigger** e **HTTP Trigger**, incluindo comunicação entre functions.

## 👥 Integrantes

- Ana Paula de Souza
- Ellen Beatriz
- Milena Damasia
- Thaynara Peron

## 👥 Turma
144-6C

## 📌 Sobre o projeto

Este Function App foi desenvolvido em Python (modelo de programação v2) e contém 4 functions:

| Function | Tipo de gatilho | Descrição |
|---|---|---|
| `timer_log_simples` | Timer Trigger | Executa periodicamente e apenas registra um log no terminal. |
| `http_echo` | HTTP Trigger | Recebe um parâmetro via query string (GET) e o exibe/retorna na resposta. |
| `http_processa` | HTTP Trigger | Recebe um valor via GET e retorna esse valor concatenado com um texto identificador. |
| `timer_chama_outra_function` | Timer Trigger | A cada execução, faz uma chamada HTTP para a function `http_processa` e registra a resposta recebida. |

## 🗂️ Estrutura do projeto

```
TAPRC-2026/
├── function_app.py               # Function principal (timer_log_simples) + registro dos blueprints
├── http_echo.py                  # Blueprint da HTTP trigger de eco
├── http_processa.py              # Blueprint da HTTP trigger alvo
├── timer_chama_outra_function.py # Blueprint da timer trigger que chama http_processa
├── host.json
├── requirements.txt
├── local.settings.json           # (não versionado — configuração local)
└── README.md
```

## ▶️ Como executar localmente

1. Instale o [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) e o [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) (emulador de storage).
2. Crie um ambiente virtual e instale as dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Inicie o Azurite (extensão do VS Code: `Azurite: Start`).
4. Rode o projeto:
   ```bash
   func start
   ```
5. Teste as HTTP triggers no navegador:
   - `http://localhost:7071/api/http_echo?nome=Thaynara`
   - `http://localhost:7071/api/http_processa?valor=teste`

## ☁️ Deploy no Azure

```bash
func azure functionapp publish <NOME-DA-SUA-FUNCTION-APP>
```

Após o deploy, configure a variável de ambiente `URL_HTTP_PROCESSA` em **Environment variables / Application settings** da Function App no Portal Azure, apontando para a URL pública real da function `http_processa` (obtida em *Get Function Url*).

## 🔗 Repositório

[github.com/thayvxss/TAPRC-2026](https://github.com/thayvxss/TAPRC-2026)
