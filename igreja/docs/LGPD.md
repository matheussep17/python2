# LGPD - plano de conformidade operacional

Este projeto nao fica "conforme a LGPD" apenas por codigo. A conformidade tambem depende de contrato, base legal, canal de atendimento, politica interna, seguranca do servidor e resposta a incidentes. O codigo agora entrega controles tecnicos para apoiar esses processos.

## Dados pessoais tratados

No licenciamento, o sistema pode tratar:

- Login da licenca.
- Hash tecnico do dispositivo.
- Nome do dispositivo, apenas se `license_send_device_name=true`.
- Datas de criacao, ativacao, validacao e validade.
- Observacoes administrativas digitadas no painel.
- Token de ativacao, usado para manter a sessao da licenca.

Evite colocar nome completo, CPF, telefone, endereco, dados de criancas ou dados sensiveis no login ou nas observacoes. Use identificadores administrativos neutros, como `IGREJA-ABC123` ou `NOTEBOOK-SALA-1`.

## Base legal e finalidade

Finalidade recomendada: controle de acesso, prevencao de uso indevido, suporte e gestao contratual das licencas.

A base legal deve ser definida pelo controlador com assessoria juridica. Para licenciamento de software, normalmente entram hipoteses como execucao de contrato, exercicio regular de direitos ou legitimo interesse, a depender do caso concreto.

## Controles implementados

- Minimizacao: o app nao envia o nome do computador por padrao.
- Transparencia: a tela de ativacao informa quais dados sao enviados.
- Seguranca: senhas de licenca sao armazenadas com hash `scrypt`; token administrativo e necessario para o painel.
- Direitos do titular: o servidor e o CLI permitem exportar dados de uma licenca.
- Eliminacao/anonimizacao: o servidor e o CLI permitem anonimizar uma licenca.
- Retencao: licencas inativas podem ser anonimizadas por prazo configuravel.
- Aviso publico: `GET /privacy` retorna finalidade, dados tratados, prazo e contato.

## Variaveis de ambiente

```powershell
$env:IGREJA_ADMIN_TOKEN="troque-por-um-token-forte"
$env:IGREJA_PRIVACY_CONTACT="privacidade@seudominio.com"
$env:IGREJA_PRIVACY_RETENTION_DAYS="1095"
```

`IGREJA_PRIVACY_RETENTION_DAYS` define por quantos dias dados de licencas inativas podem ser mantidos antes da anonimizacao por rotina.

## Operacoes administrativas

Pelo painel `/admin`:

- `Exportar dados` copia os dados de uma licenca para atendimento de solicitacao de acesso.
- `Anonimizar` remove vinculo de dispositivo, token e observacoes, preservando apenas registro operacional anonimizado.
- `Excluir` remove fisicamente a licenca ativa do banco.

Pelo CLI:

```powershell
python scripts/license_admin.py export-data IGREJA-ABC123
python scripts/license_admin.py anonymize IGREJA-ABC123 --reason "solicitacao do titular 2026-05-14"
python scripts/license_admin.py purge-inactive --retention-days 1095
```

## Pendencias fora do codigo

- Definir controlador, operador e encarregado/canal de privacidade.
- Publicar politica de privacidade para usuarios.
- Registrar bases legais, finalidades e prazos de retencao.
- Restringir acesso ao banco e ao painel administrativo.
- Usar HTTPS em producao.
- Ter rotina de backup, descarte e resposta a incidentes.
- Revisar contratos com hospedagem, distribuidores e operadores.

Referencias oficiais: Lei 13.709/2018 e materiais orientativos da ANPD sobre agentes de tratamento e encarregado.
