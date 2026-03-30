# BSOFT TMS — Documentação de Integração API

> **Base URL:** `https://nortenordeste.bsoft.app/services/index.php`  
> **Auth:** Basic Auth (`BSOFT_API_USER` / `BSOFT_API_PASS`)  
> **Headers:** `Content-Type: application/json` | `Accept: application/json`  
> **Paginação:** parâmetros `ini` (offset) e `fim` (limite) ou `limit=offset,qtd`

---


## IDs Confirmados (Norte Nordeste)

| Recurso | Descrição | ID |
|---|---|---|
| Agência Matriz | TRANSPORTADORA NORTE NORDESTE MULTIMODAL LTDA | `2` |
| Agência Filial | TRANSPORTADORA NORTE NORDESTE (FILIAL) | `3` |
| Combustível DIESEL S-10 | Diesel S10 | `2` |
| Combustível DIESEL | Diesel comum | `1` |
| Combustível GASOLINA | Gasolina | `4` |
| Combustível ETANOL | Etanol | `3` |
| Equipamento KUZ-4E30/PE | Caminhão KUZ-4E30 | `2` |
| Equipamento NIG-0F83/PI | Caminhão NIG-0F83 | `10` |
| Equipamento PPR-2G32/PE | Caminhão PPR-2G32 | `9` |
| Equipamento SOK-3I01/PE | Caminhão SOK-3I01 | `8` |
| Equipamento AZN-8C49/PE | Caminhão AZN-8C49 | `7` |
| Equipamento QCA-3B07/PE | Caminhão QCA-3B07 | `5` |
| Equipamento JOH-6843/CE | Caminhão JOH-6843 | `4` |
| Equipamento KKI-9E24/PE | Caminhão KKI-9E24 | `3` |
| Equipamento DVS-0J93/PE | Caminhão DVS-0J93 | `1` |


---

## Equipamentos — Formato do Campo

O campo `equipamento` vem no formato `PLACA/UF`. Para buscar por placa, extraia a parte antes da `/`.

```json
{ "id": "2", "equipamento": "KUZ-4E30/PE" }
```

---

## Manutenção

### Configurações / Combustíveis

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/combustiveis
```

### Configurações / Equipamentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/equipamentos
```

### Configurações / Marcas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/marcas
```

### Configurações / Modelos de Pneus

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/modelos
```

### Configurações / Ordens de Serviço

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/ordensServico
```

### Configurações / Tamanhos de Pneus

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/tamanhos
```

### Configurações / Tipos de Pneus

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/tipos
```

### Abastecimentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/abastecimentos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/manutencao/v1/abastecimentos
```

**Body:**
```json
{
    "equipamentos_id": "415",
    "dtAbastecimento": "2019-04-24",
    "ltsAbastecidos": 12,
    "valorUnitario": 1,
    "valorAbastecimento": 12,
    "localAbastecimento": "CAMPO BOM",
    "ufAbastecimento": "RS",
    "fornecedor_id": "127649",
    "programado": "S",
    "combustivel_id": "37693",
    "tipoDocumento_id": "CTE",
    "nroDoc": "123",
    "cod_rateio": "914",
    "dtVencimento": "2019-04-24",
    "outrasDespesas": 10,
    "apropOutrasDespesas": [
        {"codigo": "124" , "valor": "5"},
        {"codigo": "145" , "valor": "5"}
    ],
    "observacao": "Teste api",
    "operadorMotorista_id": "128586",
    "acrescimos": 10,
    "abatimentos": 10,
    "ordensServico_id": "74",
    "tanqueCheio": "S",
    "empresas_id": "626"
}
```

### Abastecimentos Próprios

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/abastecimentosProprios
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/manutencao/v1/abastecimentosProprios
```

**Body:**
```json
{
    "equipamentos_id": "81",
    "dtAbastecimento": "2022-07-25 14:38",
    "ltsAbastecidos": 200,
    "valorUnitario": 1,
    "valorAbastecimento": 200,
    "fornecedor_id": "121159",
    "combustivel_id": "3",
    "bombaCombustivel_id": "8",
    "odometroInicial": 150,
    "odometroFinal": 350,
    "observacao": " Observação teste via API"
}
```

### Pneus

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/manutencao/v1/pneus
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/manutencao/v1/pneus
```

**Body:**
```json
{
    "kmInicial": "1500",
    "nroSerie": "1234567",
    "marcaFogo": "ANQ-1233",
    "nroRecapagens": "12321",
    "nroRecapagensCompra": "12321",
    "profundidadeAtual": 123,
    "profundidadeCompra": 123,
    "maximoRecapagens": "150",
    "marcas_id": "17",
    "modelo_id": "7",
    "tipos_id": "16",
    "tamanho_id": "47",
    "especificacoes": "asadasd",
    "movimentacaoEntrada_id": "1674",
    "fornecedor_id": "124599",
    "dataCompra": "2022-08-09",
    "custoCompra": 20,
    "observacoes": "asdasdd",
    "tipoEstrutura": "D",
    "bandaRodagem": "D",
    "DOT": "1234 5678 9122"
}
```

---

## Controle de Viagens

### Adiantamentos

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/adiantamentos/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/adiantamentos?fim=20
```

**Parâmetros:** `fim`, `ini`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/adiantamentos
```

**Body:**
```json
{
    "valor": 10,
    "data": "2025-05-01 10:20:00",
    "empresa_id": 8,
    "motorista_id": 13
}
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/adiantamentos/lotes
```

**Body:**
```json
[
    {
        "valor": 30,
        "data": "2025-05-01 10:20:00",
        "empresa_id": 6,
        "motorista_id": 15
    },
    {
        "valor": 50,
        "data": "2025-06-01 10:20:00",
        "empresa_id": 6,
        "motorista_id": 15
    }
]
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/adiantamentos/:id
```

**Body:**
```json
{
    "valor": 32,
    "data": "2026-05-01 10:20:00",
    "observacoes": "Nova observação"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/adiantamentos/:id
```

### Despesas / Configurações / Tipos de Item

#### 🔵 `GET` — Obter um

```
GET {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item/:id
```

#### 🔵 `GET` — Obter todos

```
GET {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item?fim=100
```

**Parâmetros:** `ini`, `fim`, `descricao`, `ativo`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item/
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item/lotes
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item/:id
```

#### 🟠 `PATCH` — Atualizar

```
PATCH {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item/:id
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/despesas/configuracoes/tipos_item/:id
```

### Despesas / Modelos

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/despesas/modelos/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/despesas/modelos?limit=10
```

**Parâmetros:** `ini`, `fim`, `limit`

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/despesas/modelos/:id
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/despesas/modelos
```

**Body:**
```json
{
    "descricao": "Teste API Modelos 4",
    "seguir_numeracao_documento": false,
    "tipos_pagamento": "S"
}
```

#### 🟢 `POST` — Inserir Lotes

```
POST {BASE_URL}/controle_viagens/v1/despesas/modelos/lotes
```

**Body:**
```json
[
    {
        "descricao": "Teste API Modelos 2",
        "fornecedor_fixado_id": 19,
        "tipo_documento_fixado_id": "PED",
        "seguir_numeracao_documento": false,
        "numeracao_obrigatoria": false,
        "tipos_pagamento": ["E","S"],
        "tipo_item_sugerido_id": 7,
        "tipo_item_sugerido_editavel": false
    },
    {
        "descricao": "Teste API Modelos 4",
        "seguir_numeracao_documento": false,
        "tipos_pagamento": "S"
    }
]
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/despesas/modelos/:id
```

**Body:**
```json
{
    "descricao": "Teste API Edicao",
    "seguir_numeracao_documento": false,
    "tipos_pagamento": "S"
}
```

#### 🟠 `PATCH` — Atualizar

```
PATCH {BASE_URL}/controle_viagens/v1/despesas/modelos/:id
```

**Body:**
```json
{
    "ativo": true
}
```

### Despesas

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/despesas/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/despesas?fim=10
```

**Parâmetros:** `limit`, `ini`, `fim`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/despesas
```

**Body:**
```json
{
    "empresa_id": 4,
    "modelo_id": 32,
    "itens": [
        {
            "id": 131,
            "tipo_id": 2,
            "vinculado_a": "veiculo",
            "apropriacoes": [
                {
                    "id": 240,
                    "quantidade": 1,
                    "valor": 55,
                    "hodometro": 234324234,
                    "vinculo_id": 1
                }
            ]
        }
    ],
    "fornecedor_id": 10,
    "tipo_documento": "S/R",
    "emitida_em": "2025-05-23",
    "entrou_em": "2025-05-21",
    "tipo_pagamento": "E",
    "parcelas": [
        {
            "vencimento": "2025-06-05",
            "valor": 27.5,
            "descricao": "teste"
        },
        {
            "vencimento": "2025-07-05",
            "valor": 27.5
        }
    ],
    "observacoes": "teste"
}
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/despesas/lotes
```

**Body:**
```json
[
    {
    "empresa_id": 4,
    "modelo_id": 32,
    "itens": [
        {
            "id": 131,
            "tipo_id": 2,
            "vinculado_a": "veiculo",
            "apropriacoes": [
                {
                    "id": 240,
                    "quantidade": 1,
                    "valor": 55,
                    "hodometro": 234324234,
                    "vinculo_id": 1
                }
            ]
        }
    ],
    "fornecedor_id": 10,
    "tipo_documento": "S/R",
    "emitida_em": "2025-05-23",
    "entrou_em": "2025-05-21",
    "tipo_pagamento": "E",
    "numero_parcelas": 2,
    "parcelas": [
        {
            "vencimento": "2025-06-05",
            "valor": 27.5,
            "descricao": "teste"
        },
        {
            "vencimento": "2025-07-05",
            "valor": 27.5
        }
    ],
    "observacoes": "teste"
},{
    "empresa_id": 4,
    "modelo_id": 32,
    "itens": [
        {
            "id": 131,
            "tipo_id": 2,
            "vinculado_a": "veiculo",
            "apropriacoes": [
                {
                    "id": 240,
                    "quantidade": 1,
       ...
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/despesas/:id
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/despesas/:id
```

**Body:**
```json
{
    "empresa_id": 4,
    "modelo_id": 32,
    "itens": [
        {
            "id": 131,
            "tipo_id": 2,
            "vinculado_a": "veiculo",
            "quantidade": 1,
            "valor": 55,
            "apropriacoes": [
                {
                    "id": 240,
                    "quantidade": 1,
                    "valor": 55,
                    "hodometro": 234324234,
                    "vinculo_id": 1
                }
            ]
        }
    ],
    "fornecedor_id": 10,
    "tipo_documento": "S/R",
    "emitida_em": "2025-05-23",
    "entrou_em": "2025-05-21",
    "tipo_pagamento": "E",
    "parcelas": [
        {
            "vencimento": "2025-06-05",
            "valor": 27.5,
            "descricao": "teste"
        },
        {
            "vencimento": "2025-07-05",
            "valor": 27.5
        }
    ],
    "observacoes": "teste"
}
```

### Devoluções

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/devolucoes/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/devolucoes?fim=20
```

**Parâmetros:** `limit`, `fim`, `ini`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/devolucoes
```

**Body:**
```json
{
    "valor": 150,
    "data": "2025-05-01 10:20:00",
    "empresa_id": 8,
    "motorista_id": 13
}
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/devolucoes/lotes
```

**Body:**
```json
[
    {
        "valor": 150,
        "data": "2025-05-01 10:20:00",
        "empresa_id": 4,
        "motorista_id": 12
    },
    {
        "valor": 150,
        "data": "2025-05-01 10:20:00",
        "empresa_id": 4,
        "motorista_id": 12
    }
]
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/devolucoes/:id
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/devolucoes/:id
```

**Body:**
```json
{
    "valor": 32,
    "data": "2026-05-01 10:20:00",
    "observacoes": "Nova observação"
}
```

### Recebimentos

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/recebimentos/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/recebimentos?fim=100
```

**Parâmetros:** `fim`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/recebimentos
```

**Body:**
```json
{
    "data": "2025-05-02 00:00:00",
    "valor": 10000,
    "receita_id": 6,
    "motorista_id": 13,
    "observacoes": "Enviado via API"
}
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/recebimentos/lotes
```

**Body:**
```json
[
    {
        "data": "2025-05-02 00:00:00",
        "valor": 1,
        "receita_id": 6,
        "motorista_id": 13,
        "observacoes": "Enviado via API"
    },
    {
        "data": "2025-05-02 00:00:00",
        "valor": 1,
        "receita_id": 6,
        "motorista_id": 13,
        "observacoes": "Enviado via API"
    }
]
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/recebimentos/:id
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/recebimentos/:id
```

### Receitas

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/receitas/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/receitas?fim=10
```

**Parâmetros:** `limit`, `ini`, `fim`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/receitas
```

**Body:**
```json
{
    "empresa_id": 4,
    "cliente_id": 8,
    "tipo_documento": "NFE",
    "emitida_em": "2025-05-23",
    "entrou_em": "2025-05-21",
    "itens": [
        {
            "conta_gerencial_id": 8,
            "vinculado_a": "veiculo",
            "apropriacoes": [
                {
                    "quantidade": 1,
                    "valor": 55,
                    "vinculo_id": 1
                }
            ]
        }
    ],


    "parcelas": [
        {
            "vencimento": "2025-09-05",
            "valor": 27.5
        },
        {
            "vencimento": "2025-09-06",
            "valor": 27.5
        }
    ],
    "observacoes": "observacoes da receita"
}
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/receitas/lotes
```

**Body:**
```json
[
    {
    "empresa_id": 4,
    "cliente_id": 8,
    "tipo_documento": "NFE",
    "emitida_em": "2025-05-23",
    "entrou_em": "2025-305-21",
    "itens": [
        {
            "conta_gerencial_id": 8,
            "vinculado_a": "viagem",
            "apropriacoes": [
                {
                    "quantidade": 1,
                    "valor": 55,
                    "vinculo_id": 69
                }
            ]
        }
    ],


    "parcelas": [
        {
            "vencimento": "2025-09-05",
            "valor": 27.5
        },
        {
            "vencimento": "2025-09-06",
            "valor": 27.5
        }
    ],
    "observacoes": "observacoes da receita"
},
{
    "empresa_id": 4,
    "cliente_id": 8,
    "tipo_documento": "NFE",
    "emitida_em": "23025-05-23",
    "entrou_em": "2025-05-21",
    "itens": [
        {
            "conta_gerencial_id": 8,
            "vinculado_a": "viagem",
            "apropriacoes": [
                {
                    "quantidade": 1,
                    "valor": 55,
                    "vinculo_id": 69
                }
            ]
        }
    ],


    "parce...
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/receitas/:id
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/receitas/:id
```

**Body:**
```json
{
    "empresa_id": 4,
    "cliente_id": 8,
    "tipo_documento": "NFE",
    "emitida_em": "2025-05-23",
    "entrou_em": "2025-05-21",
    "itens": [
        {
            "conta_gerencial_id": 8,
            "vinculado_a": "veiculo",
            "apropriacoes": [
                {
                    "quantidade": 1,
                    "valor": 55,
                    "vinculo_id": 1
                }
            ]
        }
    ],


    "parcelas": [
        {
            "vencimento": "2025-09-05",
            "valor": 27.5
        },
        {
            "vencimento": "2025-09-06",
            "valor": 27.5
        }
    ],
    "observacoes": "observacoes da receita"
}
```

### Viagens / Classificações

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/viagens/classificacoes/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/viagens/classificacoes?fim=100
```

**Parâmetros:** `fim`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/viagens/classificacoes
```

**Body:**
```json
{
    "descricao": "teste"
}
```

#### 🟢 `POST` — Inserir Lotes

```
POST {BASE_URL}/controle_viagens/v1/viagens/classificacoes/lotes
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/viagens/classificacoes/:id
```

**Body:**
```json
{
    "descricao": "Classificação"
}
```

#### 🟠 `PATCH` — Atualizar

```
PATCH {BASE_URL}/controle_viagens/v1/viagens/classificacoes/:id
```

**Body:**
```json
{
    "ativo": true
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/viagens/classificacoes/:id
```

### Viagens / Documentos

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/documentos?fim=100
```

**Parâmetros:** `fim`, `ini`

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/documentos/:id_documento
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/documentos
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/documentos/lotes
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/documentos/:id_documento
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/documentos/:id_documento
```

### Viagens / Manifestos

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/manifestos?fim=100
```

**Parâmetros:** `fim`, `ini`

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/manifestos/:id_manifesto
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/manifestos/
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/manifestos/lotes
```

**Body:**
```json
[
    {
        "manifesto_id": 3
    },
    {
        "manifesto_id": 2
    }
]
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/viagens/:id_viagem/manifestos/:id_manifesto
```

### Viagens

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/viagens/:id
```

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/viagens/?fim=1
```

**Parâmetros:** `ini`, `fim`

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/viagens/
```

#### 🟢 `POST` — Inserir Lote

```
POST {BASE_URL}/controle_viagens/v1/viagens/lotes
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/controle_viagens/v1/viagens/:id
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/viagens/:id
```

### Documentos

#### 🔵 `GET` — Obter Múltiplos

```
GET {BASE_URL}/controle_viagens/v1/documentos/?fim=10
```

**Parâmetros:** `fim`, `ini`

#### 🔵 `GET` — Obter Um

```
GET {BASE_URL}/controle_viagens/v1/documentos/:id
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/controle_viagens/v1/documentos/
```

#### 🟢 `POST` — Inserir Múltiplos

```
POST {BASE_URL}/controle_viagens/v1/documentos/lotes
```

#### 🟡 `PUT` — Alterar

```
PUT {BASE_URL}/controle_viagens/v1/documentos/:id
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/controle_viagens/v1/documentos/:id
```

---

## Transporte

### Configurações / Agências

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/agencias
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/agencias
```

**Body:**
```json
{
    "pessoas_id" : "130405",
    "endereco_id" : "16871",
    "descricao" : "agencia transportadora teste agencia",
    "limitarAdiantamento" : "S",
    "maxAdiantamento" : "2.22",
    "lucroMin" : "33",
    "comissionamento" : "44",
    "percentualCustos" : "22",
    "naoAutomaticos" : "S",
    "vincularOrdem" : "S",
    "obrigaPedido" : "S",
    "tipoAgencia" : "F",
    "agAtiva" : "S",
    "classeSeguradora" : "Buonny",
    "produtoBuonny" : "05001",
    "token" : "aaaa",
    "cod_rateio" : "1444",
    "longitude" : "162.2451",
    "latitude" : "-86.8688",
    "formulaBaseCalculo" : 3,
    "cod_gerencial_receita" : "11",
    "cod_gerencial_receita_fob" : "11"
}
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/transporte/v1/agencias
```

**Body:**
```json
{
    "pessoas_id" : "130405",
    "endereco_id" : "16871",
    "descricao" : "agencia transportadora teste agencia",
    "limitarAdiantamento" : "S",
    "maxAdiantamento" : "2.22",
    "lucroMin" : "33",
    "comissionamento" : "44",
    "percentualCustos" : "22",
    "vincularOrdem" : "S",
    "obrigaPedido" : "S",
    "tipoAgencia" : "F",
    "agAtiva" : "S",
    "classeSeguradora" : "Buonny",
    "produtoBuonny" : "05001",
    "token" : "1234",
    "cod_rateio" : "1444",
    "longitude" : "162.2451",
    "latitude" : "-86.8688",
    "formulaBaseCalculo" : 3,
    "cod_gerencial_receita" : "11",
    "cod_gerencial_receita_fob" : "11"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/agencias
```

#### 🟠 `PATCH` — Editar parcialmente

```
PATCH {BASE_URL}/transporte/v1/agencias
```

**Body:**
```json
{
    "longitude" : "162.2453",
    "latitude" : "-86.8688"
}
```

### Configurações / Apólices de Seguro

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/apolicesSeguro
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/apolicesSeguro
```

**Body:**
```json
{
    "apoliceDeCliente" : "N",
    "descritivo" : "descrição da Apólice",
    "seguradora_id" : 119947,
    "contratante_id" : 120850,
    "nroApolice" : 456,
    "validaParaFiliaisContratante" : "S",
    "restringirUsoApolice" : "S",
    "sugerirApoliceQuandoContratanteTomador" : "RE",
    "dtInicioVigencia" : "2023-01-01",
    "dtFimVigencia" : "2025-01-01",
    "valorMaximoMercadoria" : 500.50,
    "premioLiquido" : 50.60,
    "descontoSobreTabela" : 10.00,
    "descontoSobreTabelaRoubo" : 10.00,
    "IOFAcidente" : 10.00,
    "IOFRoubo" : 10.00,
    "premioMinimoAcidente" : 4.00,
    "premioMinimoRoubo" : 4.00,
    "operacaoCargaDescarga" : 22.22,
    "roubo" : "S",
    "acidente" : "N",
    "calculoSeguroRelatorios" : "ambos",
    "ramoAverbacao" : "54",
    "config_formaAverbacao" : "A",
    "config_tipoAverbacao" : "W",
    "config_usuarioWS" : "vinicius",
    "config_senhaWS" : "1234",
    "config_codigoATM" : "aaa",
    "config_consideraInicioViagemComoDtEmbarque" : "N",
    "config_enviarTagRespSeg" : "SN",
    "config_enviarCpfMotorista" : "N",
    "config_ordemEnvioVeiculo" : ["SE"]
}
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/transporte/v1/apolicesSeguro
```

**Body:**
```json
{
    "apoliceDeCliente" : "N",
    "descritivo" : "nova descrição para a Apólice",
    "seguradora_id" : 119947,
    "contratante_id" : 120850,
    "nroApolice" : 445,
    "validaParaFiliaisContratante" : "S",
    "restringirUsoApolice" : "S",
    "sugerirApoliceQuandoContratanteTomador" : "RE",
    "dtInicioVigencia" : "2023-05-01",
    "dtFimVigencia" : "2028-01-01",
    "valorMaximoMercadoria" : 510.50,
    "premioLiquido" : 501.60,
    "descontoSobreTabela" : 101.00,
    "descontoSobreTabelaRoubo" : 101.00,
    "IOFAcidente" : 110.00,
    "IOFRoubo" : 10.30,
    "premioMinimoAcidente" : 44.00,
    "premioMinimoRoubo" : 54.00,
    "operacaoCargaDescarga" : 26.22,
    "roubo" : "N",
    "acidente" : "S",
    "calculoSeguroRelatorios" : "ambos",
    "config_formaAverbacao" : "A",
    "config_tipoAverbacao" : "W",
    "config_usuarioWS" : "vinicius",
    "config_senhaWS" : "1234",
    "config_codigoATM" : "aaa",
    "config_consideraInicioViagemComoDtEmbarque" : "N",
    "config_enviarTagRespSeg" : "SN",
    "config_enviarCpfMotorista" : "N",
    "config_ordemEnvioVeiculo" : ["SE"]
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/apolicesSeguro
```

### Configurações / Categorias de Veículos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/categoriasVeiculos
```

### Configurações / Espécies

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/especies
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/especies
```

**Body:**
```json
{
    "descricao" : "SACOS DE ARROZ desc",
    "capacidade" : "200",
    "ativo" : "S",
    "possuiQuebra" : "N",
    "nomeInterno" : "granel",
    "cUnid" : "03",
    "expressao" : [
        "%arroz",
        "caixa%"
    ]
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/especies
```

### Configurações / Grupos de Veículos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/gruposVeiculos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/gruposVeiculos
```

**Body:**
```json
[
    {
        "tipo_frota": "T",
        "descricao": "grupos de veículos terceiros"
    },
    {
        "tipo_frota": "P",
        "descricao": "grupos de veículos próprio",
        "empresa_id": 4,
        "campos_obrigados_tracao" : ["PRO", "AMO"]
    }
]
```

### Configurações / Marcas de Veículos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/marcaVeiculos
```

### Configurações / Naturezas de Carga

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/naturezaCargas
```

### Configurações / Naturezas de Operação

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/naturezasOperacao
```

### Configurações / Outros Valores

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/tiposValoresOutros
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/tiposValoresOutros
```

**Body:**
```json
{
    "tipo": "CF",
    "descricao": "Teste Inserir Via Api",
    "ativo": "S",
    "nomeInterno": "testeInserirViaApi",
    "imprimir": "S",
    "tipoMoeda": "S"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/tiposValoresOutros
```

### Configurações / Parâmetros de Criação de CT-e a partir de NF-e

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/paramCriaCteViaNFe
```

### Configurações / Parâmetros de Criação de MDF-e

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/parametroCriacaoManifesto
```

### Configurações / Status dos Pedidos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/statusPedidos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/statusPedidos
```

**Body:**
```json
{
    "descricao" : "teate status por api",
    "camposObrigatorios": [
        "dtColeta",
        "dtEntrega"
    ],
    "cor" : "#73BA9C",
    "corFonteKanban" : "#73BA9A",
    "corCartaoKanban" : "#73BA9B",
    "corQuadroKanban" : "#73BA9D",
    "stAtivo" : "S",
    "visivelNoKanban" : "S",
    "mostrarTotalizadorKanban" : "S",
    "permiteEmissaoOrdem" : "S",
    "ordemQuadroKanban" : 4,
    "conteudoCartaoKanban" : "TESTE CONTEUDO",
    "disponivelAprovacaoRejeicaoPeloCliente" : "S",
    "disponivelPedido" : "S",
    "disponivelCotacao" : "S",
    "permitirEdicao" : "S",
    "situacao" : "A",
    "statusAberto" : "S",
    "liberadoUso" : "S",
    "validarCadastroCliente" : "N"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/statusPedidos
```

### Configurações / Tags CT-e

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/tagsCTe
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/tagsCTe
```

**Body:**
```json
{
    "incluirNoXML" : "S",
    "qlTag" : "ObsFisco",
    "descricao" : "tag Ct-e inativa",
    "ativo" : "S"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/tagsCTe
```

### Configurações / Tipos de Ocorrências

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/tiposOcorrencias
```

### Configurações / Tipos de Operações TMS

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/tiposOperacoesTMS
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/tiposOperacoesTMS
```

**Body:**
```json
{
    "descricao": "Tipo de operação WMS",
    "rotinas": ["COT", "CTE"],
    "ativo": "S",
    "nomeInternoCotacao": "PV",
    "possuiIntegracaoEntreguei": "S"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/tiposOperacoesTMS
```

### Configurações / Tipos de Talões

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/tiposTaloes
```

### Conhecimentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/conhecimentos
```

#### 🔵 `GET` — Obter DACTE

```
GET {BASE_URL}/transporte/v1/conhecimentos/obterDacte
```

**Parâmetros:** `binario`

#### 🔵 `GET` — Obter DAMDFe

```
GET {BASE_URL}/transporte/v1/conhecimentos/obterDAMDFe
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/conhecimentos
```

**Body:**
```json
{
    "tiposTaloes_id": 312,
    "agencias_id": 148,
    "cteOS": "S",
    "pagamentoFrete": "R",
    "numeroApolice": "77777",
    "totalPrestacao": "100",
    "km": "100",
    "agenciasComissao_id": "",
    "perfisApropriacao_id": "",
    "pedidos_id": "",
    "ordensCarregamento_id": "",
    "rotaDistribuicao_id": "",
    "motorista_id": "652",
    "tipoOperacaoTMS_id": "",
    "conjuntoVeiculos_id": "",
    "veiculos_id": "28",
    "carreta_id": "29",
    "semireboque_id": "30",
    "quartoVeiculo_id": "31",
    "favorecido_id": "59",
    "remetente_id": "3",
    "enderecoRemetente_id": "15155",
    "destinatario_id": "122008",
    "enderecoDestinatario_id": "3696",
    "consignatario_id": "122008",
    "enderecoConsignatario_id": "3696",
    "redespacho_id": "123573",
    "enderecoRedespacho_id": "5412",
    "cliente_id": "",
    "enderecoCliente_id": "",
    "regraFrete_id": "359",
    "precosConhecimento_id": "",
    "operacoesMercadorias_id": "",
    "operacoes_id": "",
    "seguradora_id": "647",
    "apolice_id": "52",
    "mercadoriaOrdem_id": "",
    "regrasCarreto_id": "",
    "cfops_id": "7",
    "enderecoColeta_id": "",
    "e...
```

#### 🟢 `POST` — Inserir Via NFe

```
POST {BASE_URL}/transporte/v1/conhecimentos/viaNFe
```

**Body:**
```json
{
    "ids": [
        "4962"
    ],
    "parametroCriacaoCTe": "16",
    "tipoRateio": "P",
    "complementoPedido": "Complemento para teste API",
    "prevChegada": "2022-08-30 15:30",
    "composicaoFrete": "P",
    "pedido_id": "87",
    "tarifaDigitada": "10",
    "tarifaCalculada": "120",
    "valorFrete": "130",
    "baseCalculo": "140",
    "valorSeguroAduaneiro": "150",
    "diaria": "160",
    "valoresOutros": "170",
    "valorPedagioConhecimento": "180",
    "valorSeguro": "150",
    "gris": "190",
    "totalServico": "200",
    "totalPrestacao": "210",
    "percentualGris": "100",
    "percentualSeguro": "90",
    "outrosValores": {
        "totalizadorNF": "123.789",
        "freteValor" :"456789.456",
        "vCred": "789.123"
    }
}
```

#### 🟢 `POST` — Inserir Via XML

```
POST {BASE_URL}/transporte/v1/conhecimentos/viaXML
```

**Body:**
```json
{
	"agencia_id" : 3,
	"talao_id" : 4,
	"ctesZip" : "String base64"
}
```

### Conjuntos de Veículos / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/conjuntoVeiculos/lotes
```

**Body:**
```json
[
    {
        "motoristaId": "12",
        "removerVinculacoes": "S",
        "veiculo": "WWA-3834",
        "central": "QCF-1D64",
        "carreta": "QCF-1D44",
        "quartoVeiculo": "QCF-1D54"
    }
]
```

### Conjuntos de Veículos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/conjuntoVeiculos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/conjuntoVeiculos
```

**Body:**
```json
{
    "motoristaId": "128654",
    "removerVinculacoes": "S",
    "veiculo": "AAA-1515",
    "central": "AAA-0005",
    "carreta": "AAA-0003",
    "quartoVeiculo": "AAA-0004"
}
```

### Contêineres

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/pedidosConteiner
```

### Contratos de Frete / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/contratosFrete/lotes
```

**Body:**
```json
[
    {
        "tiposTaloes_id": 11,
        "agencias_id": 5,
        "nroRecibo": 200,
        "dtEmissao": "2025-04-02",
        "cpf_motorista": "03xxxxxxx50",
        "documento_contratado": "XXXXXXXX0001XX",
        "placa_veiculo": "XXX-XXXX",
        "placa_carreta": null,
        "placa_semireboque": null,
        "placa_quartoVeiculo": null,
        "cidadeOrigem_id": 4315602,
        "cidadeDestino_id": 4110102,
        "dtInicioViagem": "2025-04-02",
        "dtFimViagem": "2025-04-05",
        "formaPagamento": "C",
        "tipoDocumento": "CT-e",
        "valorFrete": 5000.00,
        "descontos": 0,
        "acrescimos": 0,
        "valorPedagio": 350.00,
        "valorCombustivel": 1200.00,
        "pesoChegada": 28500.000,
        "saldo": 3450.00,
        "regrasCarreto_id": 5,
        "obs": "Contrato de frete inserido via API",
        "CIOT": 360000000000050,
        "documentos": [
            {
                "id": null,
                "chaveDeAcesso": "123xxxxxxxxxxx456xxxxxxxxxxxxxxxxx789xxxxxxx",
                "tipo": "CT-e"
            },
            {
                "id": 1,
                "tipo": "OC"
       ...
```

### Contratos de Frete

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/contratosFrete
```

#### 🔵 `GET` — Obter Valores

```
GET {BASE_URL}/transporte/v1/contratosFrete/valores
```

#### 🔵 `GET` — Obter PDF

```
GET {BASE_URL}/transporte/v1/contratosFrete/pdf
```

#### 🔵 `GET` — Obter Situação Operadora

```
GET {BASE_URL}/transporte/v1/contratosFrete/operadorasCredito
```

#### 🟢 `POST` — inserir

```
POST {BASE_URL}/transporte/v1/contratosFrete
```

**Body:**
```json
{
  "tiposTaloes_id": 11,
  "agencias_id": 5,
  "nroRecibo": 200,
  "dtEmissao": "2025-04-02",
  "cpf_motorista": "03xxxxxxx50",
  "documento_contratado": "XXXXXXXX0001XX",
  "placa_veiculo": "XXX-XXXX",
  "placa_carreta": null,
  "placa_semireboque": null,
  "placa_quartoVeiculo": null,
  "cidadeOrigem_id": 4315602,
  "cidadeDestino_id": 4110102,
  "dtInicioViagem": "2025-04-02",
  "dtFimViagem": "2025-04-05",
  "formaPagamento": "C",
  "tipoDocumento": "CT-e",
  "valorFrete": 5000.00,
  "descontos": 0,
  "acrescimos": 0,
  "valorPedagio": 350.00,
  "valorCombustivel": 1200.00,
  "pesoChegada": 28500.000,
  "saldo": 3450.00,
  "regrasCarreto_id": 5,
  "obs": "Contrato de frete inserido via API",
  "CIOT": 360000000000050,
  "documentos": [
    {
      "id": null,
      "chaveDeAcesso": "123xxxxxxxxxxx456xxxxxxxxxxxxxxxxx789xxxxxxx",
      "tipo": "CT-e"
    }
  ]
}
```

### Cotações de Frete

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/cotacoesFrete
```

### Faturamentos / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/faturamentos/lotes
```

**Body:**
```json
[
    {
        "empresa_id": "4",
        "cliente_id": "152",
        "enderecoCobranca_id": "2",
        "tipo": "ADT",
        "numero": "12345",
        "data_emissao": "2022-09-15",
        "data_entrada": "2022-09-15",
        "refCliente": "Ref cliente teste via API",
        "obs": "Observação teste via API",
        "convenios_id": "2",
        "nroBoleto": "",
        "cod_cp": "M",
        "numeroParcelas": "3",
        "data_primeiro_pagamento": "2022-09-22",
        "valor_primeiro_pagamento": 0,
        "vencimentoFixo": "S",
        "intervaloDias": "",
        "diaVencimento": "10",
        "conhecimentos": [
            {
                "id": "377",
                "preenchimento_automatico": "",
                "notaFiscal": "1235",
                "freteValor": "1",
                "valorICMS": "100",
                "valoresOutros": "10",
                "valoresPedagio": "10",
                "outrosDescontos": "10",
                "pesoColeta": "10",
                "pesoChegadaReal": "20",
                "descontoQuebraPesoReal": "30",
                "cotacao": "40",
                "totalPrestacao": "500"
            }...
```

### Faturamentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/faturamentos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/faturamentos
```

**Body:**
```json
{
    "empresa_id": "4",
    "cliente_id": "3",
    "tipo": "ADT",
    "numero": "12355456",
    "data_emissao": "2024-12-17",
    "data_entrada": "2024-12-17",
    "refCliente": "Ref cliente teste via API",
    "obs": "Observação teste via API",
    "convenios_id": "2",
    "nroBoleto": "",
    "cod_cp": "M",
    "numeroParcelas": "3",
    "data_primeiro_pagamento": "2024-12-17",
    "valor_primeiro_pagamento": 0,
    "vencimentoFixo": "S",
    "intervaloDias": "",
    "diaVencimento": "10",
    "conhecimentos": [
        {
            "id": "477", 
            "preenchimento_automatico": "",
            "notaFiscal": "1235",
            "freteValor": "1",
            "valorICMS": "100",
            "valoresOutros": "10",
            "valoresPedagio": "10",
            "outrosDescontos": "10",
            "pesoColeta": "10",
            "pesoChegadaReal": "20",
            "descontoQuebraPesoReal": "30",
            "cotacao": "40",
            "totalPrestacao": "500"
        }
    ],
    "acrescimosDescontos": -10,
    "gerencial_outros": 145,
    "rateio_outros": 1,
    "internacional": "N",
    "parcelas": [
        {
            "valor"...
```

### Lotes

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/lotes
```

### Manifestos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/manifestos
```

**Parâmetros:** `dtEmissaoInicio`, `dtEmissaoFim`

#### 🔵 `GET` — Obter DAMDFe

```
GET {BASE_URL}/transporte/v1/manifestos/obterDAMDFe
```

#### 🟠 `PATCH` — Reabrir

```
PATCH {BASE_URL}/transporte/v1/manifestos/reabrir
```

#### 🟠 `PATCH` — Fechar

```
PATCH {BASE_URL}/transporte/v1/manifestos/fechar
```

**Body:**
```json
{
    "kmInicial": "10",
    "kmFinal": "25",
    "dtFechamento": "2022-06-23 08:30",
    "obs": "Observação de teste via API"
}
```

#### 🟠 `PATCH` — Encerrar

```
PATCH {BASE_URL}/transporte/v1/manifestos/encerrar
```

**Body:**
```json
{
    "fecharManifesto": "S",
    "kmInicial": "700",
    "kmFinal": "700",
    "dtFechamento": "2022-06-23 08:30",
    "obs": "Observação de teste via API"
}
```

#### 🟢 `POST` — Inserir via XML

```
POST {BASE_URL}/transporte/v1/manifestos/viaXML
```

**Body:**
```json
{
    "agencia_id": 3,
    "talao_id": 6,
    "mdfesZip": "string base64"
}
```

### NF-e Pré-Cadastrada

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/nfePreCadastrada
```

#### 🔵 `GET` — Obter DANFE

```
GET {BASE_URL}/transporte/v1/nfePreCadastrada/obterDANFE
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/nfePreCadastrada
```

**Body:**
```json
{
    "dataCarregamento": "2022-08-30",
    "emitenteEndereco_id": "15173",
    "destinatarioEndereco_id": "3673",
    "marca": "Lenovo",
    "especie_id": 3,
    "natureza_id": 6,
    "natureza": null,
    "dtNotaFiscal": "2022-08-24",
    "quantidade": 5,
    "peso": 20,
    "valor": 123,
    "vBC": 990,
    "vICMS": 990,
    "vBCST": 990,
    "vST": 990,
    "vProd": 990,
    "CFOP": "654",
    "conjunto_id": "276",
    "motorista_id": 128654,
    "veiculo_id": 1009,
    "carreta_id": null,
    "semireboque_id": null,
    "favorecido_id": 126361,
    "contrato": "S",
    "tipoDocumento": "N",
    "pinSuframa": 123,
    "cubagem": 20,
    "valorOutros": 20,
    "pedido": "Pedido teste",
    "chaveNFe": "",
    "tipoNF": "S",
    "numNotaFiscal": "286412",
    "serieNotaFiscal": "789",
    "tipoOutroDoc": 12,
    "descricaoOutroDoc": null,
    "nroOutroDoc": null,
    "fretePorConta": "R"
}
```

#### 🟢 `POST` — Inserir Via XML

```
POST {BASE_URL}/transporte/v1/nfePreCadastrada/viaXML
```

**Body:**
```json
{
    "buscaMotorista": "S",
    "arquivo": "String base64"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/nfePreCadastrada
```

### Ocorrências / Anexos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/ocorrencias/anexos
```

#### 🟢 `POST` — Inserir lotes

```
POST {BASE_URL}/transporte/v1/ocorrencias/anexos/lotes
```

**Body:**
```json
{
	"codOcorrencias": [
		"12138"
	],
	"anexos": [
		{
			"tipo": "O",
			"conteudo": "String base64",
			"extensao": ".pdf"
		}
	]
}
```

### Ocorrências

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/ocorrencias
```

**Parâmetros:** `origem`, `nroDoc`, `dtIinicio`, `dtFim`

#### 🟢 `POST` — Inserir lotes

```
POST {BASE_URL}/transporte/v1/ocorrencias/lotes
```

**Body:**
```json
[
    {
        "codOcorrencia": "6666",
        "codOcorrenciaExterno": "16316",
        "docGerouOcorrencia": "032xxx690001xx",
        "geradaPor": "APP",
        "lancadaOnline": "S",
        "codViagem": "2048",
        "codCarga": "10467",
        "dataHora": "2022-06-21 11:25:25",
        "entidade": "OC",
        "coordenadas": "-32.0537838,-52.1405557",
        "observacao": "Aqui vai uma observação",
        "dadosRecebedor" : {
            "doc": "844xxx250xx",
            "tipoDoc": "CPF",
            "recebedor": "João Paulo",
            "grauRelacionamento": 1
        },
        "dadosNFe": {
            "chaveNFe": "",
            "nroNota": "",
            "serieNota": "",
            "codConhecimento": ""
        }
    }
]
```

### Ordens de Carregamento / Mercadorias

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/ordensCarregamento/mercadorias
```

### Ordens de Carregamento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/ordensCarregamento
```

#### 🔵 `GET` — Obter OC

```
GET {BASE_URL}/transporte/v1/ordensCarregamento/obterOC
```

### Pedidos / Mercadorias

#### 🔵 `GET` — Ober

```
GET {BASE_URL}/transporte/v1/pedidos/mercadorias
```

**Parâmetros:** `ini`, `fim`, `natureza_id`, `especie_id`, `quantidade`, `marca_id`, `validade_inicial`, `validade_final`

### Pedidos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/pedidos
```

**Parâmetros:** `ini`, `agenciaId`, `talaoId`, `statusId`, `numero`, `clienteId`, `clienteDoc`, `dataIni`, `dataFim`, `refCliente`, `nroCTe`, `nroOrdem`

### Veículos / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/veiculos/lotes
```

**Body:**
```json
[
    {
        "placa": "IWV-3838",
        "proprietario": "68882348008",
        "categoriaVeiculo": "1",
        "grupoVeiculo": "29",
        "tipoRodado": "01",
        "tipoCarroceria": "03",
        "renavam": "123456789"
    },
    {
        "placa": "QAC-1H72",
        "proprietario": "68882348008",
        "categoriaVeiculo": "1",
        "grupoVeiculo": "29",
        "tipoRodado": "01",
        "tipoCarroceria": "03",
        "renavam": "123456789"
    },
    {
        "placa": "IQV-3834",
        "proprietario": "68882348008",
        "categoriaVeiculo": "1",
        "grupoVeiculo": "29",
        "tipoRodado": "01",
        "tipoCarroceria": "03",
        "renavam": "123456789"
    }
]
```

### Veículos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/transporte/v1/veiculos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/transporte/v1/veiculos
```

**Body:**
```json
{
    "placa": "INQ-1233",
    "vaga": "654123",
    "categoriaVeiculo": "1",
    "marcaVeiculo": "9",
    "modeloVeiculo": "124G",
    "grupoVeiculo": "29",
    "permitirAbastecimento": "S",
    "tipoEquipamento": "4",
    "motoristaEhProprietario": "S",
    "proprietario": "6####348008",
    "arrendatario": "03990####50",
    "transportador": "03####40050",
    "finalidade": "OS Nº 5460869553",
    "motorista": "03990####50",
    "alienado": "0399####050",
    "tipoFavorecido": "O",
    "favorecido": "03####40050",
    "estado": "RS",
    "cidade": "4315602",
    "chassi": "9BSTH4X2Z03220145",
    "certificadoReg": "99765432120",
    "renavam": "399249980",
    "anoModelo": "2010",
    "anoFabricacao": "2010",
    "cor": "Branca",
    "antt": "a1b2c3k987",
    "codRateio": "456",
    "escala": "1234",
    "capacidadeCarga": "70000",
    "quantidadeEixos": "9",
    "responsavel": "039####0050",
    "tipoRodado": "01",
    "tipoCarroceria": "03",
    "tara": "10000",
    "capM3": "30",
    "empresaRastreamento": "039####0050",
    "numeroAntena": "14",
    "tipoRastreador": "rastreador 1",
    "observacao": "Observações",
    "documentos": [...
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/transporte/v1/veiculos
```

**Body:**
```json
{
    "placa": "INQ-1233",
    "vaga": "654123",
    "categoriaVeiculo": "1",
    "marcaVeiculo": "9",
    "modeloVeiculo": "124G",
    "grupoVeiculo": "29",
    "permitirAbastecimento": "S",
    "tipoEquipamento": "4",
    "motoristaEhProprietario": "S",
    "proprietario": "03####40050",
    "arrendatario": "03####40050",
    "transportador": "039903####0",
    "finalidade": "OS Nº 5460869553",
    "motorista": "039####0050",
    "alienado": "0399####050",
    "tipoFavorecido": "O",
    "favorecido": "0399####050",
    "estado": "RS",
    "cidade": "4315602",
    "chassi": "9BSTH4X2Z03220145",
    "certificadoReg": "99765432120",
    "renavam": "399249980",
    "anoModelo": "2010",
    "anoFabricacao": "2010",
    "cor": "Branca",
    "antt": "a1b2c3k987",
    "codRateio": "456",
    "escala": "1234",
    "capacidadeCarga": "70000",
    "quantidadeEixos": "9",
    "responsavel": "03####40050",
    "tipoRodado": "01",
    "tipoCarroceria": "03",
    "tara": "10000",
    "capM3": "30",
    "empresaRastreamento": "03####40050",
    "numeroAntena": "14",
    "tipoRastreador": "rastreador 1",
    "observacao": "Observações",
    "documentos": [...
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/transporte/v1/veiculos
```

---

## Financeiro

### Configurações / Centros de Custo

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/centrosDeCusto
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/centrosDeCusto
```

**Body:**
```json
[
    {
        "descricao": "centro de custo gerencial",
        "controle_credito": "S",
        "nivelBase": "R",
        "pessoas_id": 45,
        "empresas_id": 4
    }
]
```

### Configurações / Condições de Pagamento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/condicoesPagamento
```

### Configurações / Contas Financeiras / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/contasFinanceiras/lotes
```

**Body:**
```json
[
    {
        "tipo": "caixa",
        "empresa_id": 4,
        "descricao": "API caixa",
        "usuarios": [
            4
        ]
    },
    {
        "tipo": "conta_corrente",
        "empresa_id": 4,
        "descricao": "API conta corrente",
        "cod_fiscal": 2464,
        "codFiscalCheques": 6804,
        "tipoChavePix": "A",
        "chavePix": "3412####213",
        "modoImpressao": "P",
        "st_saldo_fluxo": "N",
        "compoe_disponibilidade": "N",
        "contabilizaLancamentosDemonstrativoGerencial": "S",
        "data_implantacao": "2024-09-10",
        "saldo_implantacao": 50.09,
        "controlaCredito": "S",
        "impedirSaldoPositivo": "P",
        "bloqueiaPagSemLiberacao": "S",
        "conciliada": "S",
        "permiteLancamentosInversos": "N",
        "rejeicaoInversos": "I",
        "cod_banco": "021",
        "agencia": "0001",
        "nro_conta": "12345678",
        "limite": 100.25,
        "ultimo_cheque": 456,
        "ajustar_ultimo_cheque": "N",
        "ultimo_chequeTB": 567,
        "ajustar_ultimo_chequeTB": "N",
        "tipo_compensacao": 2,
        "dia_compensacao": 12,
        "export...
```

### Configurações / Contas Financeiras

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/contasFinanceiras
```

### Configurações / Dias de Vencimento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/configuracoes/diasVencimento
```

### Configurações / Empresas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/empresas
```

### Configurações / Família de Produtos e Serviços

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/familiaProdutosServicos
```

### Configurações / Formas de Pagamento / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/formasPagamento/lotes
```

**Body:**
```json
[
    {
        "descricao": "formas de pagamento depósito/pix",
        "tipoCobranca": "DPX",
        "contas_financeiras_id": 50
    },
    {
        "descricao": "formas de pagamento caixa",
        "tipoCobranca": "CAI",
        "formaPagamentoNFe": 99,
        "contas_financeiras_id": 51,
        "empresa_id": 4,
        "mesmoRadical": "N",
        "descricaoPagamentoNFe": "teste de pagamento",
        "juros": "50.00",
        "tipoMulta": "P",
        "percentualMulta": "50.00",
        "tituloDescontado": "N",
        "instrucaoCobranca": "teste de instrução",
        "prorrogacaoVencimento": "teste de prorrogação",
        "previsaoRecebimentoDeMais": 1234,
        "nroUltimaRemessa": 2345,
        "nro_dias_compensacao": 123,
        "protestar": "N",
        "nroDiasProtesto": 2,
        "lancarTarifas": "N",
        "possuiArquivoRetorno": "N",
        "tiposTransacaoBaixa_id": 7,
        "diasNovoVencimento": 12,
        "concedeDescArqRetorno": "N",
        "registrarAlteracoesNoBanco": "N",
        "cod_gerencialAcrescimos": 2,
        "cod_gerencialDescontos": 3,
        "cod_gerencialTarifa": 4,
        "cod_rateioTarifa": 1
   ...
```

### Configurações / Formas de Pagamento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/formasPagamento
```

### Configurações / Modelos de Nota

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/modelosNotas
```

### Configurações / Plano de Contas Gerencial

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/planoDeContasGerencial
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/planoDeContasGerencial
```

**Body:**
```json
[
    {
        "descricao" : "Raiz 9",
        "contaRetencao" : "S",
        "cod_fiscal" : "123",
        "ativo" : "N",
        "nivel" : "9."
    },
    {
        "descricao" : "9.055",
        "contaRetencao" : "S",
        "cod_fiscal" : "123",
        "ativo" : "N",
        "nivel" : "9.055"
    }
]
```

### Configurações / Plano de Contas Fiscal

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/planoDeContasFiscal
```

### Configurações / Rateios

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/rateios
```

### Configurações / Serviços

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/servicos
```

### Configurações / Tipos de Documento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/tiposDocumentos
```

### Configurações / Tipos de Pagamento / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/tiposPagamentos/lotes
```

**Body:**
```json
[
    {
        "descricao": "depósito em conta",
        "nome_interno": "deposito_conta",
        "leContaDeposito": "N",
        "convenio": "banco",
        "obrigaContaDeposito": "N",
        "nro_conta_convenio": "12344",
        "contas_financeiras_id": 51
    },
    {
        "descricao": "depósito com pix"
    }
]
```

### Configurações / Tipos de Pagamento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/tiposPagamentos
```

### Configurações / Tipos de Transação / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/tiposTransacoes/lotes
```

**Body:**
```json
[
    {
        "descricao" : "teste",
        "visivel": ["P", "R", "T"],
        "le_nro": "S",
        "exige_nro" : "S",
        "le_conta_destino" : "S",
        "auto_conciliavel" : "S",
        "nome_interno" : "chequeTB"
    }
]
```

### Configurações / Tipos de Transação

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/tiposTransacoes
```

### Conciliações Bancárias

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/conciliacao
```

**Body:**
```json
{
    "id": "123",
    "data": "2022-06-13"
}
```

### Contratos / Itens

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/contratos/itensContratos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/contratos/itensContratos
```

**Body:**
```json
{
    "identificador" : 55,
    "produtosServicos_id": "37672",
    "descricaoNf" : "nova descricao",
    "valor" : 70.00,
    "tipoCobranca" : "M",
    "dtInicio" : "2023-05-01",
    "dtFim" : "2024-05-01"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/financeiro/v1/contratos/itensContratos
```

#### 🟠 `PATCH` — Finalizar

```
PATCH {BASE_URL}/financeiro/v1/contratos/itensContratos/finalizar
```

**Body:**
```json
{
    "dtFim" : "2026-02-01"
}
```

#### 🟠 `PATCH` — Cancelar

```
PATCH {BASE_URL}/financeiro/v1/contratos/itensContratos/cancelar
```

**Body:**
```json
{
    "motivo" : 4,
    "dtIni" : "05/2023",
    "observacao" : "quero cancelar esse item de contrato",
    "sucessor" : 581
}
```

#### 🟠 `PATCH` — Suspender

```
PATCH {BASE_URL}/financeiro/v1/contratos/itensContratos/suspender
```

**Body:**
```json
{
    "motivo" : 35,
    "dtIni" : "05/2023",
    "dtFim" : "02/2027",
    "observacao" : "quero cancelar esse item de contrato"
}
```

### Contratos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/contratos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/contratos
```

**Body:**
```json
{
    "empresa_id" : "313",
    "enderecoCobranca_id" : "1636",
    "pessoas_id" : "31",
    "diaVencimento" : "01",
    "cortesia" : "N",
    "duracaoContrato" : "M",
    "classificacaoContratos" : "Outros",
    "convenios_id" : 118
}
```

#### 🟠 `PATCH` — Finalizar

```
PATCH {BASE_URL}/financeiro/v1/contratos/finalizar
```

**Body:**
```json
{
    "dtFim" : "2024-01-01"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/financeiro/v1/contratos
```

### Pagamentos / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/pagamentos/lotes
```

**Body:**
```json
[
    {
        "lancamento": {
            "tipo": "1",
            "data": "2024-12-13",
            "conta": 71,
            "historicoLancamento": "Historico teste via API",
            "transacao": "6",
            "nroTransacao" : 1234
        },
        "documentos": [
            {
                "programado" : "N",
                "tipo": "FAT",
                "pessoa": "2",
                "numero": "9999",
                "dtEmissao": "2022-06-06",
                "valor": "150.50",
                "gerencias": [
                    {"grupo":"1" , "codigo":"136", "percentual": "40"},
                    {"grupo":"1" , "codigo":"136", "percentual": "40"},
                    {"grupo":"2" , "codigo":"136", "percentual": "20"}
                ],
                "rateios": [
                    {"grupo":"1" ,"codigo":"1260", "percentual": "80"},
                    {"grupo":"2" ,"codigo":"1260", "percentual": "20"}
                ]
            }
        ]
    }
]
```

### Pagamentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/pagamentos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/pagamentos
```

**Body:**
```json
{
    "lancamento": {
        "tipo": "1",
        "data": "2024-12-13",
        "conta": 71,
        "historicoLancamento": "Historico teste via API",
        "transacao": "6",
        "nroTransacao" : 1234
    },
    "documentos": [
        {
            "programado" : "N",
            "tipo": "FAT",
            "pessoa": "2",
            "numero": "9999",
            "dtEmissao": "2022-06-06",
            "valor": "150.50",
            "gerencias": [
                {"grupo":"1" , "codigo":"136", "percentual": "40"},
                {"grupo":"1" , "codigo":"136", "percentual": "40"},
                {"grupo":"2" , "codigo":"136", "percentual": "20"}
            ],
            "rateios": [
                {"grupo":"1" ,"codigo":"1260", "percentual": "80"},
                {"grupo":"2" ,"codigo":"1260", "percentual": "20"}
            ]
        }
    ]
}
```

### Recebimentos / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/recebimentos/lotes
```

**Body:**
```json
[
    {
        "lancamento": {
            "tipo": "1",
            "data": "2022-06-03",
            "conta": 2,
            "transacao": "7",
            "nroTransacao": "12321",
            "cheque": "12311267",
            "conciliar": "S",
            "dtConciliado": "2022-06-10",
            "historicoLancamento": "Historico teste via API",
            "nominal": "128654"
        },
        "documentos": [     
            {
                "programado" : "N",    
                "tipo": "FAT",
                "pessoa": "128654",
                "numero": "1234",
                "dtEntrada": "2022-06-05",
                "dtEmissao": "2022-06-06",
                "acrescimos": "50",
                "descontos": "30",
                "valor": "150",
                "gerencias": [
                    {"grupo":"1" , "codigo":"136", "percentual": "40"},
                    {"grupo":"1" , "codigo":"136", "percentual": "40"},
                    {"grupo":"2" , "codigo":"136", "percentual": "20"}
                ],
                "rateios": [
                    {"grupo":"1" ,"codigo":"1260", "percentual": "80"},
                    {"grupo":"2" ,"c...
```

### Recebimentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/recebimentos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/recebimentos
```

**Body:**
```json
{
    "lancamento": {
        "tipo": "1",
        "data": "2022-06-03",
        "conta": 2,
        "transacao" : "6",
        "nroTransacao": "12321",
        "cheque": "12311267",
        "conciliar": "S",
        "dtConciliado": "2022-06-10",
        "historicoLancamento": "Historico teste via API",
        "nominal": "128654"
    },
    "documentos": [     
         {
            "programado" : "N",    
            "tipo": "FAT",
            "pessoa": "128654",
            "numero": "1234",
            "dtEntrada": "2022-06-05",
            "dtEmissao": "2022-06-06",
            "acrescimos": "50",
            "descontos": "30",
            "valor": "150",
            "gerencias": [
                {"grupo":"1" , "codigo":"136", "percentual": "40"},
                {"grupo":"1" , "codigo":"136", "percentual": "40"},
                {"grupo":"2" , "codigo":"136", "percentual": "20"}
            ],
            "rateios": [
                {"grupo":"1" ,"codigo":"1260", "percentual": "80"},
                {"grupo":"2" ,"codigo":"1260", "percentual": "20"}
            ],
            "gerencias_acrescimos_abatimentos": [
                {"codigo":...
```

### Tipos de Período sem Faturamento

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/tiposSuspensoesCobrancas
```

### Títulos a Pagar / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/titulosPagar/lotes
```

**Body:**
```json
[
    {
        "cod_fornecedor": 2,
        "empresa_id": 4,
        "tipo": "CTE",
        "numero": "1234",
        "quantidade_duplicatas_quitadas": "1",
        "quantidade_faturas": "1",
        "quantidade_faturas_quitadas": 0,
        "data_emissao": "2022-04-06",
        "data_entrada": "2022-04-06",
        "valor": "500",
        "previsao": "N",
        "naoFaturar": "S",   
        "data_primeiro_pagamento": "2022-05-05",
        "nro_dias": "30",
        "abatimentos": "10",
        "acrescimos": "25",
        "historico": "VALOR REFERENTE RECEITAS COM FRETES VIA API",
        "observacoes": "Observação Teste",
        "gerencias": [
            {"grupo":"1", "codigo":"136", "percentual":"20"},
            {"grupo":"1", "codigo":"145", "percentual":"10"},
            {"grupo":"2", "codigo":"145", "percentual":"70"}
        ],
        "rateios": [
            {"grupo":"1", "codigo":"1260", "percentual":"30"},
            {"grupo":"2", "codigo":"1260", "percentual":"70"}
        ],
        "duplicatas": [
            {"data_vencimento": "2024-01-01", "valor": 265},
            {"data_vencimento": "2024-01-02", "valor": 250}
        ]
   ...
```

### Títulos a Pagar

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/titulosPagar
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/titulosPagar
```

**Body:**
```json
{
    "cod_fornecedor": "128654",
	"empresa_id": "626",
    "tipo": "CTE",
    "numero": "1234",
    "nro_parcelas": "6",
    "quantidade_duplicatas_quitadas": "1",
    "quantidade_faturas": "1",
    "quantidade_faturas_quitadas": 0,
    "data_emissao": "2022-04-06",
    "data_entrada": "2022-04-06",
    "valor": "500",
    "previsao": "N",
    "naoFaturar": "S",   
    "data_primeiro_pagamento": "2022-05-05",
    "nro_dias": "30",
    "abatimentos": "10",
    "acrescimos": "25",
    "historico": "VALOR REFERENTE RECEITAS COM FRETES VIA API",
    "observacoes": "Observação Teste",
	"gerencias": [
		{"grupo":"1", "codigo":"136", "percentual":"20"},
		{"grupo":"1", "codigo":"145", "percentual":"10"},
		{"grupo":"2", "codigo":"145", "percentual":"70"}
	],
	"rateios": [
		{"grupo":"1", "codigo":"1260", "percentual":"30"},
		{"grupo":"2", "codigo":"1260", "percentual":"70"}
	]
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/financeiro/v1/titulosPagar
```

### Títulos a Receber / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/titulosReceber/lotes
```

**Body:**
```json
[
    {
        "cod_cliente": 2,
        "empresa_id": 4,
        "tipo": "CTE",
        "numero": "1234",
        "nro_parcelas": "6",
        "quantidade_duplicatas_quitadas": "1",
        "quantidade_faturas": "1",
        "quantidade_faturas_quitadas": 0,
        "data_emissao": "2022-04-06",
        "data_entrada": "2022-04-06",
        "valor": "800",
        "previsao": "N",
        "naoFaturar": "S",   
        "data_primeiro_pagamento": "2022-05-05",
        "nro_dias": "30",
        "abatimentos": "10",
        "acrescimos": "25",
        "historico": "VALOR REFERENTE RECEITAS COM FRETES VIA API",
        "observacoes": "Observação Teste",
        "referencia": "07/2024",
        "gerencias": [
            {"grupo":"1", "codigo":"136", "percentual":"20"},
            {"grupo":"1", "codigo":"145", "percentual":"10"},
            {"grupo":"2", "codigo":"145", "percentual":"70"}
        ],
        "rateios": [
            {"grupo":"1", "codigo":"1260", "percentual":"30"},
            {"grupo":"2", "codigo":"1260", "percentual":"70"}
        ],
        "duplicatas": [
            {"data_vencimento": "2024-01-01", "valor": 800},
            {"...
```

### Títulos a Receber

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/titulosReceber
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/titulosReceber
```

**Body:**
```json
{
    "cliente_doc": "XXX",
	"empresa_doc": "XXX",
    "tipo": "CTE",
    "numero": "1234",
    "nro_parcelas": "6",
    "quantidade_duplicatas_quitadas": "1",
    "quantidade_faturas": "1",
    "quantidade_faturas_quitadas": 0,
    "data_emissao": "2022-04-06",
    "data_entrada": "2022-04-06",
    "valor": "800.00",
    "previsao": "N",
    "naoFaturar": "S",   
    "data_primeiro_pagamento": "2022-05-05",
    "nro_dias": "30",
    "abatimentos": "10",
    "acrescimos": "25",
    "historico": "VALOR REFERENTE RECEITAS COM FRETES VIA API",
    "observacoes": "Observação Teste",
    "duplicatas": [
        {
            "data_vencimento": "2024-11-06",
            "valor": "500.00"
        },
        {
            "data_vencimento": "2024-12-06",
            "valor": "500.00"
        }
    ],
    "referencia": "07/2024",
	"gerencias": [
		{"grupo":"1", "codigo":"136", "percentual":"20"},
		{"grupo":"1", "codigo":"145", "percentual":"10"},
		{"grupo":"2", "codigo":"145", "percentual":"70"}
	],
	"rateios": [
		{"grupo":"1", "codigo":"1260", "percentual":"30"},
		{"grupo":"2", "codigo":"1260", "percentual":"70"}
	]
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/financeiro/v1/titulosReceber
```

### Transferências

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/financeiro/v1/transferencia
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/financeiro/v1/transferencia
```

**Body:**
```json
{
    "origem": {
        "data": "2022-06-10",
        "tipo": "C",
        "conta": "12",
        "transacao": "12",
        "cheque": "123456789",
        "predatado": "2022-06-10",
        "nroTransacao": "12312321"
    },
    "destino": {
        "conta":"66",
        "valor": "123.00",
        "historico": "historico via API",
        "observacao": "Transferencia via API"
    }
}
```

---

## Ordem de Serviço

### Ações

#### 🟢 `POST` — inserir

```
POST {BASE_URL}/os/v1/ordensServico/acao
```

**Body:**
```json
{
    "acao":"teste"
}
```

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/ordensServico/acao
```

### Agendamentos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/ordensServico/agendamentos
```

### Categorias

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/categorias
```

### Históricos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/ordensServico/historicos
```

### Materiais

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/ordensServico/materiais
```

### Ordens de Serviços

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/ordensServico
```

#### 🟠 `PATCH` — Editar

```
PATCH {BASE_URL}/os/v1/ordensServico
```

**Body:**
```json
{
    "prioridade": 4,
    "codigoPt": "41",
    "tiposId": 2,
    "statusId": 5,
    "categoriaId": 1,
    "auditada": true,
    "osOriginal": 1,
    "pessoaContato": 2,
    "dtAbertura": "2024-07-23 00:00:00",
    "dtOrcamento": "2024-06-01 00:00:00",
    "dtAprovacao": "2024-07-23 00:00:00",
    "dtPrevisaoFechamento": "2024-08-15",
    "descricao": "=> Troca de oleo\nPlano de manutenção - Carro - Troca de oleo - TROCA\n\nProcedimentos:\nTroca de óleo, troca de filtro e etc\n\nServiços:\nNenhum serviço vinculado\n\nComponentes:\nNenhum componente vinculado",
    "observacoes": "Observação Exemplo",
    "dtFechamento": "2024-08-08"
}
```

### Produtos e Serviços

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/ordensServico/produtosServicos
```

### Status

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/status
```

### Tipos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/os/v1/tipos
```

---

## Pessoas

### Arquivos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/arquivos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/arquivos
```

**Body:**
```json
{
    "tipo" : "I",
    "descricao" : "imagem perfil",
    "extensao": "png",
    "arquivo" : "String Base64"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/pessoas/v1/pessoas/arquivos
```

### Contas para Depósito / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/contasDepositos/lotes
```

**Body:**
```json
[{
    "codPessoa": 12,
    "conta" : {
        "cod_banco" : "104",
        "agencia" : "1234",
        "tipoConta" : "C",
        "nroConta" : "123123213",
        "dvContaCorrente" : "1",
        "tipoCorrentista" : "O",
        "operacao" : "123"
    },
    "pix" : {
        "tipoChavePix" : "A",
        "chavePix" : "53999768323@gmail.com"
    },
    "preferencial" : "S",
    "outro_favorecido" : "S",
    "docOutroFavorecido" : "12345",
    "nomeOutroFavorecido" : "vinicius"
}]
```

### Contas para Depósito

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/contasDepositos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/contasDepositos
```

**Body:**
```json
{
    "conta" : {
        "cod_banco" : "104",
        "agencia" : "1234",
        "tipoConta" : "C",
        "nroConta" : "123123213",
        "dvContaCorrente" : "1",
        "tipoCorrentista" : "O",
        "operacao" : "123"
    },
    "pix" : {
        "tipoChavePix" : "A",
        "chavePix" : "53999768323@gmail.HDHDHDF"
    },
    "preferencial" : "S",
    "outro_favorecido" : "S",
    "docOutroFavorecido" : "12345",
    "nomeOutroFavorecido" : "vinicius"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/pessoas/v1/pessoas/contasDepositos
```

### Contatos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/contatos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/contatos
```

**Body:**
```json
[{
    "nome": "Marcos",
    "cpf": "",
    "fone": "(00) 0000-0000",
    "celular": "(00) 0000-0000",
    "email": "",
    "msn": "msn@msn",
    "skype": "@skype",
    "funcao": "analista",
    "contatoPreferencial": "S",
    "observacao": "observação 01",
    "ativo": "S"
}]
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/pessoas/v1/pessoas/contatos
```

### Endereços / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/enderecos/lotes
```

**Body:**
```json
[{
    "codPessoa": 12,
    "tipoEndereco": "N",
    "cep": "96202-090",
    "bairro": "Bairro São José",
    "cidade": "Rio Grande",
    "estado": "RS",
    "numero": "100",
    "complemento": "Ap. 201",
    "logradouro": "Av da paz",
    "cobrancaPreferencial": "N",
    "enderecoPreferencial": "S",
    "codIBGE": "4325602",
    "inscricaoMunicipal": "ISENTO",
    "inscricaoEstadual": "ISENTO",
    "inscricaoEstadualNaoContribuinte": "S",
    "telefone1": "(00) 0000-0000",
    "telefone2": "(00) 0000-0000"
},
{
    "codPessoa": 12,
    "tipoEndereco": "N",
    "cep": "96202-090",
    "bairro": "Bairro São ACENTUAÇÃO",
    "cidade": "Rio Grande",
    "estado": "RS",
    "numero": "100",
    "complemento": "Ap. 201",
    "logradouro": "Av da paz",
    "cobrancaPreferencial": "N",
    "enderecoPreferencial": "S",
    "codIBGE": "4315602",
    "inscricaoMunicipal": "ISENTO",
    "inscricaoEstadual": "ISENTO",
    "inscricaoEstadualNaoContribuinte": "S",
    "telefone1": "(00) 0000-0000",
    "telefone2": "(00) 0000-0000"
}]
```

### Endereços

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/enderecos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/enderecos
```

**Body:**
```json
[{
    "tipoEndereco": "N",
    "cep": "96202-090",
    "bairro": "Bairro Centro",
    "cidade": "Rio Grande",
    "estado": "RS",
    "numero": "100",
    "complemento": "Ap. 201",
    "logradouro": "Av da paz",
    "cobrancaPreferencial": "N",
    "enderecoPreferencial": "S",
    "codIBGE": "4315602",
    "inscricaoMunicipal": "ISENTO",
    "inscricaoEstadual": "ISENTO",
    "inscricaoEstadualNaoContribuinte": "S",
    "telefone1": "(00) 0000-0000",
    "telefone2": "(00) 0000-0000"
}]
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/pessoas/v1/pessoas/enderecos
```

### Estrangeiras

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/estrangeiras
```

**Body:**
```json
[
    {
        "nome": "empresa do uruguais",
        "grupos": [
            "proprietariosVeiculos"
        ],
        "RNTRC": 12345678
    },
    {
        "nome": "empresa da argentinas",
        "documento": "12345678"
    }
]
```

### Físicas / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/fisicas/lotes
```

**Body:**
```json
[
    {
	"cpf": "2258####003",
	"nome": "Exemplo",
    "sobrenome": "Sobrenome Exemplo",
    "sexo": "M",
    "dtNascimento": "1996-05-02",
	"grupos": [
		"motoristas",
		"proprietariosVeiculos",
		"fornecedores",
        "clientes"
	],
	"identificador": "12345",
	"mae": "Mãe Exemplo da Silva",
	"pai": "Pai Exemplo da Silva",
	"estadoCivil": "S",
	"apelido": "DF",
	"grauInstruTrabalhador": "07",
	"profissao": "2",
	"naturalidade": "Rio dos Índios",
	"naturalidadeUF": "RS",
	"nacionalidade": "Brasil",
	"numeroRG": "25xxxx081",
	"emissaoRG": "2010-11-30",
	"orgaoExpedidorRG": "SJS",
	"matriculaINSS": "26xxxxx22887",
	"numeroCTPS": "559xxxxx362",
	"serieCTPS": "0030",
	"ufExpedicaoCTPS": "RS",
	"alvara": "123456",
	"telResidencial": "(00) 0000-0000",
	"celular": "(00) 0000-00000",
	"outrosTels": "(00) 0000-00000",
	"site": "http://www.meusite.com.br",
	"email": "contato@empresa.com.br;contato2@empresa.com.br",
	"emailCobranca": "cobranca@empresa.com.br",
	"emailCotacaoEstoque": "estoque@empresa.com.br",
	"emailOcorrenciasTransporte": "transporte@empresa.com.br",
	"observacoes": "Exemplo de observações",
	"RNTRC": "12xxxx78",
	"dependentesIRRF":...
```

### Físicas / Profissões

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/fisicas/profissoes
```

### Físicas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/fisicas
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/fisicas
```

**Body:**
```json
{
	"cpf": "34xxxxxxx70",
	"nome": "Exemplo",
    "sobrenome": "Sobrenome Exemplo",
    "sexo": "M",
    "dtNascimento": "1996-05-02",
	"grupos": [
		"proprietariosVeiculos",
		"fornecedores",
        "clientes"
	],
	"identificador": "12345",
	"mae": "Mãe Exemplo da Silva",
	"pai": "Pai Exemplo da Silva",
	"estadoCivil": "S",
	"apelido": "DF",
	"grauInstruTrabalhador": "07",
	"profissao": "2",
	"naturalidade": "Rio dos Índios",
	"naturalidadeUF": "RS",
	"nacionalidade": "Brasil",
	"numeroRG": "25xxxx081",
	"emissaoRG": "2010-11-30",
	"orgaoExpedidorRG": "SJS",
	"matriculaINSS": "26xxxxx22887",
	"numeroCTPS": "559xxxxx362",
	"serieCTPS": "0030",
	"ufExpedicaoCTPS": "RS",
	"alvara": "123456",
	"telResidencial": "(00) 0000-0000",
	"celular": "(00) 0000-00000",
	"outrosTels": "(00) 0000-00000",
	"site": "http://www.meusite.com.br",
	"email": "contato@empresa.com.br;contato2@empresa.com.br",
	"emailCobranca": "cobranca@empresa.com.br",
	"emailCotacaoEstoque": "estoque@empresa.com.br",
	"emailOcorrenciasTransporte": "transporte@empresa.com.br",
	"observacoes": "Exemplo de observações",
	"RNTRC": "12xxxx78",
	"dependentesIRRF": "1",
	"tipoTransportad...
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/pessoas/v1/pessoas/fisicas
```

**Body:**
```json
{
	"cpf": "34xxxxxxx70",
	"nome": "Exemplo",
    "sobrenome": "Sobrenome Exemplo",
    "sexo": "M",
    "dtNascimento": "1996-05-02",
	"grupos": [
		"motoristas",
		"proprietariosVeiculos",
		"fornecedores",
        "clientes"
	],
	"identificador": "12345",
	"mae": "Mãe Exemplo da Silva",
	"pai": "Pai Exemplo da Silva",
	"estadoCivil": "S",
	"apelido": "DF",
	"grauInstruTrabalhador": "07",
	"profissao": "2",
	"naturalidade": "Rio dos Índios",
	"naturalidadeUF": "RS",
	"nacionalidade": "Brasil",
	"numeroRG": "25xxxx081",
	"emissaoRG": "2010-11-30",
	"orgaoExpedidorRG": "SJS",
	"matriculaINSS": "26xxxxx22887",
	"numeroCTPS": "559xxxxx362",
	"serieCTPS": "0030",
	"ufExpedicaoCTPS": "RS",
	"alvara": "123456",
	"telResidencial": "(00) 0000-0000",
	"celular": "(00) 0000-00000",
	"outrosTels": "(00) 0000-00000",
	"site": "http://www.meusite.com.br",
	"email": "contato@empresa.com.br;contato2@empresa.com.br",
	"emailCobranca": "cobranca@empresa.com.br",
	"emailCotacaoEstoque": "estoque@empresa.com.br",
	"emailOcorrenciasTransporte": "transporte@empresa.com.br",
	"observacoes": "Exemplo de observações",
	"RNTRC": "12xxxx78",
	"dependentesIRRF": "1",
...
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/pessoas/v1/pessoas/fisicas
```

### Grupos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/grupos/geral
```

### Jurídicas / Lotes

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/juridicas/lotes
```

**Body:**
```json
[
    {
        "cnpj": "18.0##.###/0001-47",
        "razaoSocial": "Empresa Exemplo",
        "nomeFantasia": "Empresa Exemplo",
        "enquadramento": "s",
        "grupos": [
            "fornecedores"
        ],
        "identificador": "",
        "telComercial": "(00) 0000-0000",
        "celular": "(00) 00000-0000",
        "site": "www.empresaExemplo.com.br",
        "email": "faleconosco@empresaExemplo.com.br",
        "emailCobranca": "",
        "emailCotacaoEstoque": "",
        "emailOcorrenciasTransporte": "",
        "observacoes": "Exemplo de observações",
        "codISSQNAtividadePrincipal" : "7927"
    }, {
        "cnpj": "85.2##.###/0001-03",
        "razaoSocial": "Empresa Exemplo",
        "nomeFantasia": "Empresa Exemplo",
        "enquadramento": "s",
        "grupos": [
            "fornecedores"
        ],
        "identificador": "",
        "telComercial": "(00) 0000-0000",
        "celular": "(00) 00000-0000",
        "site": "www.empresaExemplo.com.br",
        "email": "faleconosco@empresaExemplo.com.br",
        "emailCobranca": "",
        "emailCotacaoEstoque": "",
        "emailOcorrenciasTransporte": "",
   ...
```

### Jurídicas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/pessoas/v1/pessoas/juridicas
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/pessoas/v1/pessoas/juridicas
```

**Body:**
```json
{
	"cnpj": "19.###.##4/0001-46",
	"razaoSocial": "Empresa Exemplo",
    "nomeFantasia": "Empresa Exemplo",
    "enquadramento": "s",
	"grupos": [
		"fornecedores"
    ],
	"identificador": "",
	"telComercial": "(00) 0000-0000",
	"celular": "(00) 00000-0000",
	"site": "www.empresaExemplo.com.br",
	"email": "faleconosco@empresaExemplo.com.br",
	"emailCobranca": "",
	"emailCotacaoEstoque": "",
	"emailOcorrenciasTransporte": "",
	"observacoes": "Exemplo de observações",
    "codISSQNAtividadePrincipal" : "7927"
}
```

#### 🟡 `PUT` — Editar

```
PUT {BASE_URL}/pessoas/v1/pessoas/juridicas
```

**Body:**
```json
{
	"cnpj": "19.###.##4/0001-46",
	"razaoSocial": "Empresa Exemplo",
    "nomeFantasia": "Empresa Exemplo",
    "enquadramento": "s",
	"grupos": [
		"fornecedores"
    ],
	"identificador": "",
	"telComercial": "(00) 0000-0000",
	"celular": "(00) 00000-0000",
	"site": "www.empresaExemplo.com.br",
	"email": "faleconosco@empresaExemplo.com.br",
	"emailCobranca": "",
	"emailCotacaoEstoque": "",
	"emailOcorrenciasTransporte": "",
	"observacoes": "Exemplo de observações",
    "codISSQNAtividadePrincipal" : "7927"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/pessoas/v1/pessoas/juridicas
```

---

## Recursos

### Recursos / Grupos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/recursos/v1/recursos/grupos
```

### Recursos / Inatividades

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/recursos/v1/recursos/inatividades
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/recursos/v1/recursos/inatividades
```

**Body:**
```json
{
    "data_inicial" : "2022-12-07",
    "data_final" : "2022-12-08"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/recursos/v1/recursos/inatividades
```

### Recursos / IPsAcesso

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/recursos/v1/recursos/ipsAcesso
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/recursos/v1/recursos/ipsAcesso
```

**Body:**
```json
{
    "ip" : "%4"
}
```

#### 🔴 `DELETE` — Remover

```
DELETE {BASE_URL}/recursos/v1/recursos/ipsAcesso
```

### Recursos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/recursos/v1/recursos
```

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/recursos/v1/recursos
```

**Body:**
```json
{
    "descricao": "Fulano",
    "categorias": [
        "DIR",
        "GER",
        "OPE",
        "CON",
        "COM",
        "RCD",
        "RCQ"
    ],
    "email": "fulano.ciclano@hotmail.com.br",
    "telefone": "991XXXX31",
    "perfilAcesso": [
        "S",
        "R",
        "A"
    ],
    "nome": "fulano",
    "gerarSenhaAleatoria": "S"
}
```

#### 🟠 `PATCH` — Editar parcialmente

```
PATCH {BASE_URL}/recursos/v1/recursos
```

**Body:**
```json
{
    "forcarTrocaSenha": "N",
    "validadeTrocaSenha": "2025-09-10"
}
```

#### 🟠 `PATCH` — Ativar

```
PATCH {BASE_URL}/recursos/v1/recursos/ativar
```

#### 🟠 `PATCH` — Inativar

```
PATCH {BASE_URL}/recursos/v1/recursos/inativar
```

#### 🟠 `PATCH` — AdicionarGrupo

```
PATCH {BASE_URL}/recursos/v1/recursos/adicionarGrupo
```

**Body:**
```json
{
    "grupos": [
        107
    ]
}
```

#### 🟠 `PATCH` — RemoverGrupo

```
PATCH {BASE_URL}/recursos/v1/recursos/removerGrupo
```

**Body:**
```json
{
    "grupos" : [
        107,
        109
    ]
}
```

---

## e-Doc

### Arquivos PDF / CT-es emitidos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/PDFDocumentosFiscais/CTesEmitidos
```

### Arquivos PDF / CT-es recebidos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/PDFDocumentosFiscais/CTesRecebidos
```

### Arquivos PDF / NF-es emitidas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/PDFDocumentosFiscais/NFesEmitidas
```

### Arquivos PDF / NF-es recebidas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/PDFDocumentosFiscais/NFesRecebidas
```

### Arquivos PDF / MDF-e

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/PDFDocumentosFiscais/MDFe
```

### Arquivos XML / CT-es emitidos

#### 🟢 `POST` — Obter

```
POST {BASE_URL}/eDoc/v1/XMLDocumentosFiscais/CTesEmitidos
```

### Arquivos XML / CT-es recebidos

#### 🟢 `POST` — Obter

```
POST {BASE_URL}/eDoc/v1/XMLDocumentosFiscais/CTesRecebidos
```

### Arquivos XML / NF-es emitidas

#### 🟢 `POST` — Obter

```
POST {BASE_URL}/eDoc/v1/XMLDocumentosFiscais/NFesEmitidas
```

### Arquivos XML / NF-es recebidas

#### 🟢 `POST` — Obter

```
POST {BASE_URL}/eDoc/v1/XMLDocumentosFiscais/NFesRecebidas
```

### Arquivos XML / MDF-e

#### 🟢 `POST` — Obter

```
POST {BASE_URL}/eDoc/v1/XMLDocumentosFiscais/MDFe
```

### Chaves de acesso / CT-es emitidos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v2/chavesDeAcesso/CTesEmitidos
```

### Chaves de acesso / CT-es recebidos

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/chavesDeAcesso/CTesRecebidos
```

### Chaves de acesso / NF-es emitidas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v2/chavesDeAcesso/NFesEmitidas
```

### Chaves de acesso / NF-es recebidas

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/chavesDeAcesso/NFesRecebidas
```

### Chaves de acesso / MDF-e

#### 🔵 `GET` — Obter

```
GET {BASE_URL}/eDoc/v1/chavesDeAcesso/MDFe
```

#### 🔵 `GET` — Obter v2

```
GET {BASE_URL}/eDoc/v2/chavesDeAcesso/MDFe
```

### Eventos / CT-e

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/eDoc/v1/eventos/CTe
```

**Body:**
```json
{
    "eventosZip" : "String base64"
}
```

### Eventos / MDF-e

#### 🟢 `POST` — Inserir

```
POST {BASE_URL}/eDoc/v1/eventos/MDFe
```

**Body:**
```json
{
    "eventosZip" : "String base64"
}
```

---
