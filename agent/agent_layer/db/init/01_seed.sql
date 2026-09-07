-- ============================================================
-- TechPulse Assistant — Seed Data
-- Tables: repos, tags, authors
-- ============================================================

-- Drop tables if they exist (clean slate)
DROP TABLE IF EXISTS authors CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS repos CASCADE;

-- ============================================================
-- TABLE: repos
-- ============================================================
CREATE TABLE repos (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    language    VARCHAR(100),
    stars       INTEGER DEFAULT 0,
    description TEXT,
    saved_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: tags
-- ============================================================
CREATE TABLE tags (
    id      SERIAL PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    tag     VARCHAR(100) NOT NULL
);

-- ============================================================
-- TABLE: authors
-- ============================================================
CREATE TABLE authors (
    id       SERIAL PRIMARY KEY,
    repo_id  INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    username VARCHAR(150) NOT NULL,
    role     VARCHAR(50) NOT NULL
);

-- ============================================================
-- SEED: repos (50 rows)
-- ============================================================
INSERT INTO repos (name, language, stars, description, saved_at) VALUES
('langchain-ai/langchain',           'Python',     92000, 'Build context-aware reasoning applications using LLMs.',                          '2024-01-10 09:00:00'),
('langchain-ai/langgraph',           'Python',     11200, 'Build stateful, multi-actor LLM applications as graphs.',                         '2024-01-12 10:30:00'),
('crewAIInc/crewAI',                 'Python',     21500, 'Framework for orchestrating role-playing autonomous AI agents.',                   '2024-02-01 08:15:00'),
('microsoft/autogen',                'Python',     33800, 'Multi-agent conversation framework for building LLM workflows.',                   '2024-02-03 11:00:00'),
('openai/openai-python',             'Python',     23100, 'Official Python library for the OpenAI API.',                                      '2024-02-05 14:00:00'),
('anthropics/anthropic-sdk-python',  'Python',      3400, 'Official Python SDK for the Anthropic Claude API.',                               '2024-02-07 09:45:00'),
('run-llama/llama_index',            'Python',     37200, 'Data framework for LLM-based applications over custom data.',                     '2024-02-10 13:00:00'),
('hwchase17/chroma',                 'Python',     16800, 'Open-source embedding database for AI-native applications.',                      '2024-03-01 10:00:00'),
('qdrant/qdrant',                    'Rust',       21300, 'High-performance vector database with extended filtering support.',                '2024-03-03 08:00:00'),
('qdrant/qdrant-client',             'Python',      2100, 'Python client library for Qdrant vector database.',                               '2024-03-05 09:30:00'),
('tiangolo/fastapi',                 'Python',     76400, 'High performance web framework for building APIs with Python.',                   '2024-03-08 12:00:00'),
('pydantic/pydantic',                'Python',     21800, 'Data validation using Python type annotations.',                                  '2024-03-10 14:30:00'),
('modelcontextprotocol/python-sdk',  'Python',      5600, 'Official Python SDK for the Model Context Protocol (MCP).',                      '2024-03-12 11:15:00'),
('modelcontextprotocol/servers',     'TypeScript',  8900, 'Reference MCP server implementations for common integrations.',                  '2024-03-14 10:00:00'),
('huggingface/transformers',         'Python',    133000, 'State-of-the-art ML models for NLP, vision, and audio.',                         '2024-03-15 09:00:00'),
('huggingface/datasets',             'Python',     19400, 'Datasets and evaluation metrics for ML models.',                                  '2024-03-17 11:00:00'),
('ollama/ollama',                    'Go',         92000, 'Run large language models locally with a simple CLI.',                            '2024-03-20 08:30:00'),
('vllm-project/vllm',                'Python',     38700, 'High-throughput LLM inference and serving engine.',                              '2024-03-22 13:00:00'),
('microsoft/semantic-kernel',        'C#',         23100, 'SDK for integrating AI models into conventional apps.',                          '2024-03-25 10:45:00'),
('stanfordnlp/dspy',                 'Python',     20800, 'Framework for algorithmically optimizing LM prompts.',                           '2024-03-27 09:00:00'),
('BerriAI/litellm',                  'Python',     15900, 'Call 100+ LLMs using the OpenAI API format.',                                    '2024-04-01 10:00:00'),
('guidance-ai/guidance',             'Python',     19300, 'Guidance language for controlling language models.',                              '2024-04-03 11:30:00'),
('explosion/spacy',                  'Python',     30100, 'Industrial-strength NLP library for Python.',                                    '2024-04-05 09:00:00'),
('facebookresearch/faiss',           'C++',        32600, 'Library for efficient similarity search and clustering of dense vectors.',       '2024-04-07 14:00:00'),
('celery/celery',                    'Python',     25100, 'Distributed task queue for Python applications.',                                 '2024-04-10 08:00:00'),
('encode/uvicorn',                   'Python',      9200, 'Lightning-fast ASGI server for Python.',                                         '2024-04-12 10:00:00'),
('sqlalchemy/sqlalchemy',            'Python',      9600, 'Python SQL toolkit and Object Relational Mapper.',                               '2024-04-14 13:00:00'),
('tortoise/tortoise-orm',            'Python',      4500, 'Familiar asyncio ORM for Python inspired by Django.',                            '2024-04-16 11:00:00'),
('alembic/alembic',                  'Python',      3100, 'Database migration tool for SQLAlchemy.',                                        '2024-04-18 09:00:00'),
('encode/httpx',                     'Python',     13500, 'Fully featured HTTP client for Python with async support.',                      '2024-04-20 14:30:00'),
('pytest-dev/pytest',                'Python',     12300, 'Simple, powerful testing framework for Python.',                                 '2024-04-22 10:00:00'),
('docker/compose',                   'Go',         34200, 'Define and run multi-container Docker applications.',                            '2024-04-24 08:00:00'),
('grafana/grafana',                  'TypeScript', 64500, 'Open observability platform for metrics, logs, and traces.',                     '2024-04-26 11:00:00'),
('prometheus/prometheus',            'Go',         56100, 'Monitoring system and time series database.',                                    '2024-04-28 09:30:00'),
('redis/redis',                      'C',          66800, 'In-memory data structure store used as cache and message broker.',               '2024-05-01 10:00:00'),
('apache/kafka',                     'Java',       28900, 'Distributed event streaming platform for high-performance pipelines.',           '2024-05-03 08:15:00'),
('aws/aws-cdk',                      'TypeScript', 11600, 'Cloud Development Kit for defining cloud infrastructure in code.',               '2024-05-05 14:00:00'),
('hashicorp/terraform',              'Go',         43200, 'Infrastructure as code tool for cloud provisioning.',                            '2024-05-07 10:30:00'),
('kubernetes/kubernetes',            'Go',        110000, 'Production-grade container orchestration platform.',                             '2024-05-09 09:00:00'),
('argoproj/argo-workflows',          'Go',         14900, 'Kubernetes-native workflow engine for parallel jobs.',                           '2024-05-11 11:00:00'),
('nickvdyck/webbrowser',             'Python',       880, 'Tiny Python library to open URLs in the web browser.',                          '2024-05-13 13:00:00'),
('jina-ai/jina',                     'Python',     20900, 'Build multimodal AI services with cloud-native architecture.',                   '2024-05-15 10:00:00'),
('deepset-ai/haystack',              'Python',     18200, 'LLM orchestration framework for building AI pipelines.',                         '2024-05-17 09:00:00'),
('prefecthq/prefect',                'Python',     16400, 'Workflow orchestration for data and ML pipelines.',                              '2024-05-19 08:30:00'),
('apache/airflow',                   'Python',     38000, 'Platform to programmatically author, schedule, and monitor workflows.',          '2024-05-21 14:00:00'),
('pocketbase/pocketbase',            'Go',         40100, 'Open source backend in a single file with REST API.',                           '2024-05-23 10:00:00'),
('supabase/supabase',                'TypeScript', 73200, 'Open source Firebase alternative with Postgres.',                               '2024-05-25 09:00:00'),
('trpc/trpc',                        'TypeScript', 36000, 'End-to-end typesafe APIs made easy with TypeScript.',                           '2024-05-27 11:00:00'),
('vercel/ai',                        'TypeScript', 12800, 'Build AI-powered streaming text and chat UIs with React.',                      '2024-05-29 13:00:00'),
('mozilla/llamafile',                'C++',        20700, 'Run LLMs locally as a single distributable executable.',                        '2024-05-31 10:00:00');


-- ============================================================
-- SEED: tags
-- ============================================================
INSERT INTO tags (repo_id, tag) VALUES
-- langchain
(1, 'llm'), (1, 'ai'), (1, 'agent'), (1, 'rag'),
-- langgraph
(2, 'llm'), (2, 'agent'), (2, 'graph'), (2, 'workflow'),
-- crewai
(3, 'agent'), (3, 'llm'), (3, 'multi-agent'), (3, 'ai'),
-- autogen
(4, 'agent'), (4, 'llm'), (4, 'multi-agent'), (4, 'microsoft'),
-- openai-python
(5, 'llm'), (5, 'openai'), (5, 'sdk'), (5, 'ai'),
-- anthropic sdk
(6, 'llm'), (6, 'claude'), (6, 'sdk'), (6, 'ai'),
-- llama_index
(7, 'llm'), (7, 'rag'), (7, 'ai'), (7, 'indexing'),
-- chroma
(8, 'vector-db'), (8, 'embedding'), (8, 'rag'), (8, 'ai'),
-- qdrant
(9, 'vector-db'), (9, 'embedding'), (9, 'search'), (9, 'rust'),
-- qdrant-client
(10, 'vector-db'), (10, 'sdk'), (10, 'python'),
-- fastapi
(11, 'api'), (11, 'python'), (11, 'web'), (11, 'devtools'),
-- pydantic
(12, 'python'), (12, 'validation'), (12, 'devtools'),
-- mcp python-sdk
(13, 'mcp'), (13, 'sdk'), (13, 'ai'), (13, 'agent'),
-- mcp servers
(14, 'mcp'), (14, 'integration'), (14, 'devtools'),
-- transformers
(15, 'llm'), (15, 'nlp'), (15, 'ai'), (15, 'huggingface'),
-- datasets
(16, 'nlp'), (16, 'ai'), (16, 'data'), (16, 'huggingface'),
-- ollama
(17, 'llm'), (17, 'local-ai'), (17, 'devtools'),
-- vllm
(18, 'llm'), (18, 'inference'), (18, 'serving'), (18, 'gpu'),
-- semantic-kernel
(19, 'llm'), (19, 'agent'), (19, 'microsoft'), (19, 'sdk'),
-- dspy
(20, 'llm'), (20, 'prompt'), (20, 'optimization'), (20, 'ai'),
-- litellm
(21, 'llm'), (21, 'api'), (21, 'proxy'), (21, 'devtools'),
-- guidance
(22, 'llm'), (22, 'prompt'), (22, 'ai'),
-- spacy
(23, 'nlp'), (23, 'python'), (23, 'ai'),
-- faiss
(24, 'vector-db'), (24, 'search'), (24, 'embedding'), (24, 'ml'),
-- celery
(25, 'python'), (25, 'queue'), (25, 'distributed'),
-- uvicorn
(26, 'python'), (26, 'asgi'), (26, 'web'), (26, 'devtools'),
-- sqlalchemy
(27, 'python'), (27, 'database'), (27, 'orm'), (27, 'devtools'),
-- tortoise-orm
(28, 'python'), (28, 'database'), (28, 'async'), (28, 'orm'),
-- alembic
(29, 'python'), (29, 'database'), (29, 'migrations'),
-- httpx
(30, 'python'), (30, 'http'), (30, 'async'), (30, 'devtools'),
-- pytest
(31, 'python'), (31, 'testing'), (31, 'devtools'),
-- docker compose
(32, 'docker'), (32, 'devops'), (32, 'container'),
-- grafana
(33, 'observability'), (33, 'monitoring'), (33, 'devops'),
-- prometheus
(34, 'monitoring'), (34, 'devops'), (34, 'metrics'),
-- redis
(35, 'database'), (35, 'cache'), (35, 'distributed'),
-- kafka
(36, 'streaming'), (36, 'distributed'), (36, 'data'),
-- aws cdk
(37, 'cloud'), (37, 'aws'), (37, 'infrastructure'),
-- terraform
(38, 'cloud'), (38, 'infrastructure'), (38, 'devops'),
-- kubernetes
(39, 'devops'), (39, 'container'), (39, 'orchestration'),
-- argo workflows
(40, 'devops'), (40, 'kubernetes'), (40, 'workflow'),
-- nickvdyck/webbrowser
(41, 'python'), (41, 'utility'),
-- jina
(42, 'llm'), (42, 'ai'), (42, 'multimodal'), (42, 'search'),
-- haystack
(43, 'llm'), (43, 'rag'), (43, 'ai'), (43, 'agent'),
-- prefect
(44, 'workflow'), (44, 'mlops'), (44, 'data'),
-- airflow
(45, 'workflow'), (45, 'data'), (45, 'orchestration'),
-- pocketbase
(46, 'database'), (46, 'api'), (46, 'backend'),
-- supabase
(47, 'database'), (47, 'backend'), (47, 'postgres'), (47, 'devtools'),
-- trpc
(48, 'api'), (48, 'typescript'), (48, 'devtools'),
-- vercel/ai
(49, 'llm'), (49, 'ai'), (49, 'typescript'), (49, 'streaming'),
-- llamafile
(50, 'llm'), (50, 'local-ai'), (50, 'ai');


-- ============================================================
-- SEED: authors
-- ============================================================
INSERT INTO authors (repo_id, username, role) VALUES
-- langchain
(1, 'hwchase17',        'owner'),
(1, 'baskaryan',        'contributor'),
(1, 'agola11',          'contributor'),
-- langgraph
(2, 'hwchase17',        'owner'),
(2, 'nfcampos',         'contributor'),
-- crewai
(3, 'joaomdmoura',      'owner'),
(3, 'lorenzejohn',      'contributor'),
-- autogen
(4, 'sonichi',          'owner'),
(4, 'qingyunwu',        'contributor'),
(4, 'yiranwu0',         'contributor'),
-- openai python
(5, 'stainless-bot',    'owner'),
(5, 'rattrayalex',      'contributor'),
-- anthropic sdk
(6, 'stainless-bot',    'owner'),
(6, 'aaditya-anthropic','contributor'),
-- llama_index
(7, 'jerryjliu',        'owner'),
(7, 'logan-markewich',  'contributor'),
(7, 'leehanchung',      'contributor'),
-- chroma
(8, 'jeffhuys',         'owner'),
(8, 'atroyn',           'contributor'),
-- qdrant
(9, 'generall',         'owner'),
(9, 'agladkikh',        'contributor'),
-- qdrant client
(10, 'generall',        'owner'),
(10, 'coszio',          'contributor'),
-- fastapi
(11, 'tiangolo',        'owner'),
(11, 'adriangb',        'contributor'),
-- pydantic
(12, 'samuelcolvin',    'owner'),
(12, 'davidhewitt',     'contributor'),
-- mcp python-sdk
(13, 'jspahrsummers',   'owner'),
(13, 'dsp-ant',         'contributor'),
-- mcp servers
(14, 'jspahrsummers',   'owner'),
(14, 'phdye',           'contributor'),
-- transformers
(15, 'sgugger',         'owner'),
(15, 'LysandreJik',     'contributor'),
(15, 'patrickvonplaten','contributor'),
-- datasets
(16, 'lhoestq',         'owner'),
(16, 'mariosasko',      'contributor'),
-- ollama
(17, 'mxyng',           'owner'),
(17, 'jmorganca',       'contributor'),
(17, 'dhiltgen',        'contributor'),
-- vllm
(18, 'WoosukKwon',      'owner'),
(18, 'zhuohan123',      'contributor'),
-- semantic-kernel
(19, 'shawncal',        'owner'),
(19, 'dmytrostruk',     'contributor'),
-- dspy
(20, 'okhat',           'owner'),
(20, 'arnav-singhvi',   'contributor'),
-- litellm
(21, 'ishaan-jaff',     'owner'),
(21, 'krrishdholakia',  'contributor'),
-- guidance
(22, 'slundberg',       'owner'),
(22, 'riedgar-ms',      'contributor'),
-- spacy
(23, 'honnibal',        'owner'),
(23, 'ines',            'contributor'),
-- faiss
(24, 'mdouze',          'owner'),
(24, 'wickedfoo',       'contributor'),
-- celery
(25, 'ask',             'owner'),
(25, 'thedrow',         'contributor'),
-- uvicorn
(26, 'tomchristie',     'owner'),
(26, 'Kludex',          'contributor'),
-- sqlalchemy
(27, 'zzzeek',          'owner'),
(27, 'CaselIT',         'contributor'),
-- tortoise orm
(28, 'grigi',           'owner'),
(28, 'Aerendir',        'contributor'),
-- alembic
(29, 'zzzeek',          'owner'),
(29, 'deepaks4077',     'contributor'),
-- httpx
(30, 'tomchristie',     'owner'),
(30, 'florimondmanca',  'contributor'),
-- pytest
(31, 'nicoddemus',      'owner'),
(31, 'The-Compiler',    'contributor'),
-- docker compose
(32, 'aiordache',       'owner'),
(32, 'glours',          'contributor'),
-- grafana
(33, 'marefr',          'owner'),
(33, 'dprokop',         'contributor'),
-- prometheus
(34, 'beorn7',          'owner'),
(34, 'roidelapluie',    'contributor'),
-- redis
(35, 'oranagra',        'owner'),
(35, 'itamarhaber',     'contributor'),
-- kafka
(36, 'ijuma',           'owner'),
(36, 'dajac00',         'contributor'),
-- aws cdk
(37, 'rix0rrr',         'owner'),
(37, 'otaviomacedo',    'contributor'),
-- terraform
(38, 'mitchellh',       'owner'),
(38, 'apparentlymart',  'contributor'),
-- kubernetes
(39, 'thockin',         'owner'),
(39, 'liggitt',         'contributor'),
(39, 'deads2k',         'contributor'),
-- argo
(40, 'alexec',          'owner'),
(40, 'tcnghia',         'contributor'),
-- nickvdyck
(41, 'nickvdyck',       'owner'),
-- jina
(42, 'bwanglzu',        'owner'),
(42, 'nan-wang',        'contributor'),
-- haystack
(43, 'bogdankostic',    'owner'),
(43, 'anakin87',        'contributor'),
-- prefect
(44, 'zanieb',          'owner'),
(44, 'desertaxle',      'contributor'),
-- airflow
(45, 'mik-laj',         'owner'),
(45, 'turbaszek',       'contributor'),
-- pocketbase
(46, 'ganigeorgiev',    'owner'),
(46, 'presentator',     'contributor'),
-- supabase
(47, 'kiwicopple',      'owner'),
(47, 'thor-ragnarok',   'contributor'),
-- trpc
(48, 'KATT',            'owner'),
(48, 'nicholasgasior',  'contributor'),
-- vercel/ai
(49, 'nicoalbanese',    'owner'),
(49, 'lgrammel',        'contributor'),
-- llamafile
(50, 'jart',            'owner'),
(50, 'trholding',       'contributor');


-- ============================================================
-- Quick verification queries (comment out before running)
-- ============================================================
-- SELECT COUNT(*) FROM repos;    -- expect 50
-- SELECT COUNT(*) FROM tags;     -- expect ~180
-- SELECT COUNT(*) FROM authors;  -- expect ~110

-- Sample join: AI-tagged repos with owner and star count
-- SELECT r.name, r.language, r.stars, a.username AS owner, array_agg(t.tag) AS tags
-- FROM repos r
-- JOIN authors a ON a.repo_id = r.id AND a.role = 'owner'
-- JOIN tags t ON t.repo_id = r.id
-- GROUP BY r.name, r.language, r.stars, a.username
-- HAVING 'ai' = ANY(array_agg(t.tag))
-- ORDER BY r.stars DESC;
