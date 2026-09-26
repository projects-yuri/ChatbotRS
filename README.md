# VAARChatbot

Chatbot documental desenvolvido para o **Projeto Integrador PI-5** utilizando arquitetura **RAG (Retrieval-Augmented Generation)**.

O sistema recupera informações da documentação armazenada no projeto e utiliza os trechos encontrados como contexto para gerar respostas fundamentadas nas fontes disponíveis.

A versão atual está especializada principalmente no fluxo educacional do Rio Grande do Sul:

```text
SAERS → IMERS → PRE → IPM → distribuição do ICMS municipal
```

A base documental pode ser alterada ou ampliada pela pasta `raw/`, sem necessidade de treinar novamente o modelo de linguagem.

---

# Arquitetura

O fluxo principal da aplicação é:

```text
Documentos em raw/
        ↓
src/ingestion.py
        ↓
Extração e limpeza do texto
        ↓
Chunking
        ↓
Embeddings
        ↓
ChromaDB
        ↓
Pergunta do usuário
        ↓
Busca semântica
        ↓
Recuperação de candidatos
        ↓
Reranking e deduplicação
        ↓
Construção do contexto
        ↓
LLM via OpenRouter
        ↓
Resposta + fontes
        ↓
Streamlit
```

O modelo de linguagem **não é treinado novamente com os documentos**.

Os documentos são transformados em representações vetoriais e armazenados no ChromaDB. Quando o usuário realiza uma pergunta, o sistema procura os trechos semanticamente mais relacionados e envia somente o contexto recuperado ao modelo de linguagem.

---

# Base documental atual

A versão atual do projeto foi otimizada para trabalhar principalmente com informações relacionadas a:

- **SAERS** — Sistema de Avaliação do Rendimento Escolar do Rio Grande do Sul;
- **IMERS** — Índice Municipal da Qualidade da Educação do Rio Grande do Sul;
- **PRE** — Participação no Rateio da Cota-Parte da Educação;
- **Porte municipal**;
- **IPM** — Índice de Participação dos Municípios;
- relação entre educação e distribuição do **ICMS municipal**.

O projeto originalmente também trabalhou com documentos relacionados a **Fundeb e VAAR**, mas o chatbot somente consegue responder adequadamente sobre esses temas quando os respectivos documentos estão presentes e indexados na pasta `raw/`.

---

# Tecnologias utilizadas

O projeto utiliza:

- **Python** — linguagem principal;
- **Streamlit** — interface web;
- **ChromaDB** — banco vetorial;
- **Sentence Transformers** — geração de embeddings;
- **LangChain / cliente OpenAI** — integração com o modelo;
- **OpenRouter** — acesso ao LLM;
- **PyPDF** — extração de texto de arquivos PDF;
- **python-dotenv** — leitura das variáveis de ambiente.

Modelo de linguagem configurado:

```text
z-ai/glm-5.2:free
```

Modelo de embeddings:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

# Configuração atual do RAG

A configuração atual utiliza:

```text
CHUNK_SIZE = 900
CHUNK_OVERLAP = 180

TOP_K = 12
CANDIDATE_K = 28
MAX_CONTEXT_CHUNKS = 14

INDEX_BATCH_SIZE = 48
```

## CHUNK_SIZE

Define aproximadamente o tamanho máximo dos trechos criados durante a indexação.

```text
900 caracteres
```

## CHUNK_OVERLAP

Define a quantidade de conteúdo compartilhado entre chunks consecutivos.

```text
180 caracteres
```

O overlap ajuda a evitar perda de contexto quando uma informação aparece exatamente na divisão entre dois chunks.

## CANDIDATE_K

Quantidade de candidatos recuperados inicialmente:

```text
28
```

O sistema busca mais documentos do que realmente serão utilizados para permitir uma segunda etapa de seleção.

## TOP_K

Quantidade alvo de trechos após a recuperação e o reranking:

```text
12
```

## MAX_CONTEXT_CHUNKS

Limite máximo de trechos utilizados na construção do contexto:

```text
14
```

---

# Recuperação e reranking

O sistema não utiliza apenas a primeira resposta do ChromaDB.

Depois da busca vetorial, os resultados passam por etapas adicionais de seleção.

O sistema considera:

- distância semântica;
- palavras da pergunta presentes no trecho;
- relevância da fonte;
- nome do documento;
- deduplicação;
- diversidade entre fontes.

Fluxo:

```text
Pergunta
   ↓
Busca ampliada
   ↓
28 candidatos
   ↓
Reranking
   ↓
Deduplicação
   ↓
Diversificação
   ↓
Melhores trechos
   ↓
Contexto
```

Essa estratégia reduz a chance de vários chunks quase iguais dominarem o contexto enviado ao modelo.

---

# Estrutura do projeto

```text
VAARChatbot/
│
├── raw/
│   └── documentos utilizados pelo RAG
│
├── src/
│   ├── __init__.py
│   ├── ingestion.py
│   ├── rag.py
│   └── settings.py
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# Principais arquivos

## `app.py`

Responsável pela interface web utilizando **Streamlit**.

Principais funções:

- receber perguntas;
- manter histórico da conversa;
- chamar o sistema RAG;
- mostrar a resposta;
- mostrar os trechos utilizados;
- mostrar as fontes recuperadas;
- apresentar informações sobre a base;
- permitir reconstrução do índice quando necessário.

---

## `src/ingestion.py`

Responsável pela preparação e indexação da documentação.

Fluxo:

```text
Arquivo
  ↓
Leitura
  ↓
Extração
  ↓
Limpeza
  ↓
Chunking
  ↓
Embedding
  ↓
ChromaDB
```

O processo também mantém metadados como:

```text
source
type
page
chunk
```

Arquivos CSV podem incluir também informações como:

```text
row
uf
entity
codigo_ibge
```

---

## `src/rag.py`

Responsável pela recuperação dos documentos e geração da resposta.

Fluxo principal:

```text
Pergunta
   ↓
retrieve()
   ↓
Busca semântica
   ↓
Expansão da consulta
   ↓
Reranking
   ↓
Deduplicação
   ↓
build_context()
   ↓
OpenRouter
   ↓
LLM
   ↓
Resposta
```

O modelo recebe:

```text
Pergunta
+
Trechos recuperados
```

e gera a resposta utilizando o contexto fornecido.

---

## `src/settings.py`

Centraliza as configurações do projeto.

Entre elas:

```text
RAW_DIR
CHROMA_DIR
COLLECTION_NAME
EMBEDDING_MODEL
CHUNK_SIZE
CHUNK_OVERLAP
INDEX_BATCH_SIZE
TOP_K
CANDIDATE_K
MAX_CONTEXT_CHUNKS
INDEX_VERSION
```

---

# Formatos de documentos

A versão atual do processo de ingestão trabalha principalmente com:

```text
.pdf
.txt
.csv
```

Os documentos devem ser colocados em:

```text
raw/
```

> Arquivos Markdown (`.md`) somente serão indexados caso o `ingestion.py` seja configurado para aceitar essa extensão.

---

# Como executar o projeto

## 1. Requisitos

Para executar localmente é necessário:

- Python 3.11 ou superior;
- Git;
- conexão com a internet;
- chave de API da OpenRouter.

---

# 2. Clonar o repositório

Abra o CMD, PowerShell ou terminal do Visual Studio Code.

Execute:

```bash
git clone https://github.com/projects-yuri/VAARChatbot.git
```

Entre na pasta:

```bash
cd VAARChatbot
```

---

# 3. Criar o ambiente virtual

Execute:

```bash
python -m venv .venv
```

## Windows CMD

```cmd
.venv\Scripts\activate
```

## Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

## Linux / macOS

```bash
source .venv/bin/activate
```

Quando ativado corretamente, deverá aparecer algo semelhante a:

```text
(.venv) C:\Users\usuario\VAARChatbot>
```

---

# 4. Instalar as dependências

Execute:

```bash
pip install -r requirements.txt
```

As bibliotecas necessárias estão listadas no arquivo:

```text
requirements.txt
```

---

# 5. Configurar a OpenRouter

Na raiz do projeto, crie:

```text
.env
```

Exemplo:

```env
OPENROUTER_API_KEY=SUA_CHAVE_OPENROUTER

OPENROUTER_MODEL=z-ai/glm-5.2:free

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

CHUNK_SIZE=900
CHUNK_OVERLAP=180

TOP_K=12
CANDIDATE_K=28
MAX_CONTEXT_CHUNKS=14

INDEX_BATCH_SIZE=48
```

Substitua:

```text
SUA_CHAVE_OPENROUTER
```

pela sua chave.

> **Nunca publique sua chave da OpenRouter no GitHub.**

O arquivo:

```text
.env
```

deve permanecer no `.gitignore`.

---

# 6. Banco vetorial

O projeto utiliza:

```text
ChromaDB
```

A versão atual permite configurar o diretório através da variável:

```text
CHROMA_DIR
```

Por padrão, o `settings.py` utiliza um diretório temporário compatível com o ambiente do Streamlit Cloud.

Essa alteração foi feita para evitar erros do SQLite como:

```text
attempt to write a readonly database
```

e:

```text
no such table: tenants
```

Caso seja necessário definir manualmente um diretório local, pode ser utilizada uma variável como:

```env
CHROMA_DIR=data/chroma
```

---

# 7. Adicionar os documentos

Coloque os arquivos que deseja utilizar dentro de:

```text
raw/
```

Exemplo:

```text
raw/
├── Base_Consolidada_SAERS_IMERS_PRE.pdf
└── outros_documentos.pdf
```

A pasta `raw/` é a base de conhecimento efetiva do chatbot.

Se um documento não estiver nessa pasta, ele não será utilizado pelo processo normal de indexação.

---

# 8. Criar o índice

Antes da primeira utilização, execute:

```bash
python -m src.ingestion --reset
```

Esse processo:

1. verifica os documentos;
2. extrai o texto;
3. limpa o conteúdo;
4. cria os chunks;
5. gera os embeddings;
6. cria ou abre o ChromaDB;
7. grava os vetores;
8. armazena os metadados;
9. registra o estado do índice.

---

# 9. Executar o chatbot

Após criar o índice:

```bash
streamlit run app.py
```

Normalmente a aplicação será aberta em:

```text
http://localhost:8501
```

Caso o navegador não abra automaticamente, copie o endereço e acesse manualmente.

---

# Streamlit Cloud

Para realizar deploy no Streamlit Cloud, as informações privadas devem ser adicionadas em:

```text
Settings
→ Secrets
```

Exemplo:

```toml
OPENROUTER_API_KEY = "SUA_CHAVE"

OPENROUTER_MODEL = "z-ai/glm-5.2:free"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 180

TOP_K = 12
CANDIDATE_K = 28
MAX_CONTEXT_CHUNKS = 14

INDEX_BATCH_SIZE = 48
```

A chave da OpenRouter não deve ser colocada diretamente no código ou enviada ao GitHub.

---

# Como uma pergunta é processada

Exemplo:

```text
Como o porte do município influencia a PRE?
```

O sistema executa aproximadamente:

```text
Pergunta
   ↓
Embedding / busca semântica
   ↓
Consultas auxiliares
   ↓
ChromaDB
   ↓
28 candidatos
   ↓
Reranking
   ↓
Deduplicação
   ↓
Diversificação
   ↓
Construção do contexto
   ↓
OpenRouter
   ↓
GLM
   ↓
Resposta
   ↓
Fontes
```

---

# Controle contra alucinações

O chatbot foi configurado para priorizar respostas baseadas nos documentos recuperados.

O modelo deve:

- responder utilizando o contexto recuperado;
- evitar inventar leis;
- evitar inventar percentuais;
- evitar inventar fórmulas;
- evitar inventar municípios ou valores;
- não transformar um exemplo específico em regra geral;
- informar quando a documentação não contém informações suficientes.

A ideia principal é:

```text
O ChromaDB encontra.
O Sentence Transformer representa semanticamente.
O LLM explica.
```

---

# Diferença entre os principais conceitos

## Chunking

Divide documentos grandes em partes menores.

```text
Documento
↓
Chunk 1
Chunk 2
Chunk 3
```

---

## Tokenização

Divide o texto em unidades que podem ser processadas pelo modelo de linguagem.

---

## Embedding

Transforma um trecho de texto em uma representação numérica que captura características semânticas.

```text
Texto
↓
Vetor
```

---

## ChromaDB

Armazena os vetores e permite localizar trechos semanticamente semelhantes à pergunta.

---

## Reranking

Reorganiza os resultados recuperados para priorizar os trechos mais úteis antes de montar o contexto.

---

## RAG

Combina:

```text
Recuperação de informação
+
Modelo de linguagem
```

Fluxo simplificado:

```text
Pergunta
↓
Busca documental
↓
Contexto
↓
LLM
↓
Resposta
```

---

# Atualizar a base documental

Caso os documentos da pasta `raw/` sejam modificados, execute novamente:

```bash
python -m src.ingestion --reset
```

Depois:

```bash
streamlit run app.py
```

---

# Problemas comuns

## `429`

Exemplo:

```text
429 Too Many Requests
```

Esse erro normalmente está relacionado aos limites do modelo gratuito utilizado através da OpenRouter.

Não significa necessariamente que o código do RAG esteja incorreto.

---

## `attempt to write a readonly database`

Erro relacionado ao SQLite utilizado pelo ChromaDB quando o diretório não possui permissões de escrita adequadas.

A versão atual utiliza uma estratégia de diretório temporário para reduzir esse problema no Streamlit Cloud.

---

## `no such table: tenants`

Pode ocorrer quando existe um banco Chroma antigo ou incompatível com a versão atual.

Uma solução é reconstruir o índice:

```bash
python -m src.ingestion --reset
```

---

## Índice inexistente

Caso o sistema informe que o índice não existe ou precisa ser reconstruído:

```bash
python -m src.ingestion --reset
```

---

# Execução rápida

```bash
git clone https://github.com/projects-yuri/VAARChatbot.git

cd VAARChatbot

python -m venv .venv
```

Windows CMD:

```cmd
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Configure:

```text
.env
```

Depois:

```bash
python -m src.ingestion --reset
```

E execute:

```bash
streamlit run app.py
```

Abra:

```text
http://localhost:8501
```

---

# Resumo da arquitetura

```text
raw/
 ↓
ingestion.py
 ↓
Limpeza
 ↓
Chunking (900 / 180)
 ↓
Sentence Transformers
 ↓
Embeddings
 ↓
ChromaDB
 ↓
28 candidatos
 ↓
Reranking
 ↓
TOP_K = 12
 ↓
Contexto
 ↓
OpenRouter
 ↓
GLM 5.2
 ↓
app.py
 ↓
Streamlit
 ↓
Usuário
```

---

# Projeto

**Projeto Integrador PI-5**

Chatbot documental com arquitetura RAG aplicado à documentação educacional do Rio Grande do Sul.

Repositório:

https://github.com/projects-yuri/VAARChatbot
