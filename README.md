# PISID – Integração de Dados com MQTT, MongoDB e MySQL

## Descrição do projeto Grupo - 34

Este projeto foi desenvolvido no âmbito da unidade curricular de PISID e tem como objetivo recolher, armazenar e encaminhar dados gerados durante a execução do jogo MazeRun.

A solução implementada utiliza uma arquitetura baseada em **MQTT**, **MongoDB** e **MySQL**, permitindo receber eventos em tempo real, armazená-los temporariamente numa base de dados NoSQL e, posteriormente, encaminhá-los para integração noutros sistemas.

Os principais tipos de eventos tratados são:
- movimentos dos jogadores;
- sons;
- temperaturas.

## Arquitetura geral

O funcionamento do sistema está dividido em duas fases principais:

### S1 – MQTT para MongoDB
O script **S1** subscreve os tópicos MQTT onde são publicados os eventos do jogo e armazena esses dados no MongoDB, em coleções distintas consoante o tipo de evento.

### S2 – MongoDB para MQTT / MySQL
O script **S2** faz verificações periódicas às coleções do MongoDB. Antes de enviar um documento, é feita uma verificação temporal para confirmar se já existe um registo igual tratado recentemente. Se isso acontecer, o documento é ignorado. Caso contrário, é enviado normalmente e fica registado o instante em que foi processado.

Esta abordagem permite evitar duplicações imediatas entre verificações consecutivas, sem impedir que eventos semelhantes possam voltar a ser tratados mais tarde, caso correspondam a novas ocorrências legítimas.

## Estrutura do repositório

```text
.
├── README.md
├── scripts/
│   ├── S1_mqtt_to_mongo.py
│   ├── S2.py
│   ├── teste_mqtt.py
│   └── verificar_mongo.py
└── sql/
