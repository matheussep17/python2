# Solução de Problemas: Erro HTTP 403

## Problema
Você está recebendo o erro: **"HTTP Error 403: Forbidden"** ao tentar baixar vídeos do YouTube.

## Causas Possíveis

### 1. **Vídeo Restrito por Região (Geo-blocking)**
Alguns vídeos estão disponíveis apenas em determinados países. 

**Solução:**
- Teste com outro vídeo que você sabe estar disponível em sua região
- Considere usar uma VPN (aunque isso pode viola os Termos de Serviço do YouTube)

### 2. **Vídeo Restrito por Idade**
Conteúdo classificado como 18+ que requer login.

**Solução:**
- Faça login em sua conta do YouTube no navegador
- Verifique se sua idade está corretamente configurada na conta
- O app tentará usar as cookies do seu navegador na próxima tentativa

### 3. **Vídeo Privado ou Removido**
O vídeo pode ter sido removido pelo proprietário.

**Solução:**
- Verifique se o link está correto
- Tente acessar o vídeo diretamente no navegador
- Se não conseguir ver no navegador, o app também não conseguirá

### 4. **Problema de Autenticação/Sessão**
Sua sessão do YouTube pode ter expirado.

**Solução:**
- Abra o YouTube no seu navegador e faça login novamente
- Aguarde 5-10 minutos antes de tentar novamente no app
- O app usará as cookies de sessão do navegador

### 5. **YouTube Bloqueou Sua Conexão**
Muitas requisições em pouco tempo podem desencadear limites de taxa.

**Solução:**
- Aguarde 10-30 minutos antes de tentar novamente
- Não tente baixar múltiplos vídeos simultaneamente
- Considere usar um proxy diferente ou conexão VPN

## Passos de Troubleshooting

### Passo 1: Testar no Navegador
```
1. Copie o link do vídeo
2. Abra em um navegador (Chrome, Firefox, Edge)
3. Se funcionar no navegador, o problema é com o app
4. Se não funcionar no navegador, o vídeo é realmente restrito
```

### Passo 2: Fazer Login no YouTube
```
1. Abra o YouTube no seu navegador padrão
2. Clique em "Fazer login" no canto superior
3. Insira suas credenciais
4. Retorne ao app Igreja e tente novamente
```

### Passo 3: Atualizar yt-dlp
O erro pode estar relacionado a uma desatualização do yt-dlp.

```
1. No app, clique em "Atualizar yt-dlp" (botão no canto superior)
2. Aguarde a atualização completar
3. Tente novamente
```

Ou via terminal:
```bash
pip install --upgrade yt-dlp
```

### Passo 4: Limpar Cookies/Cache
```
1. Feche completamente o app Igreja
2. Abra o YouTube no navegador
3. Faça logout (Seu avatar > Fazer logout)
4. Feche o navegador
5. Reabra o app e tente novamente
```

## Erro do Pytubefix

Se também aparecer: **"[WinError 2] O sistema não pode encontrar o arquivo especificado"**

Isso significa que o `pytubefix` (fallback) também falhou. O pytubefix é um sistema alternativo quando yt-dlp não consegue funcionar.

**Soluções:**
- Verifique se o Windows Defender ou antivírus não está bloqueando o app
- Tente reiniciar o computador
- Desinstale e reinstale o pytubefix:
  ```bash
  pip uninstall pytubefix
  pip install pytubefix
  ```

## Ainda Não Funciona?

Se nenhuma solução funcionou:

1. **Tente com outro vídeo** - Verifique se é específico deste vídeo
2. **Reinicie o app** - Às vezes ajuda fechar e reabrir
3. **Atualize todas as dependências:**
   ```bash
   pip install --upgrade yt-dlp pytubefix
   ```
4. **Verifique a conexão:** Teste sua conexão de internet
5. **Relatório de Bug:** Se o problema persistir, considere relatar ao repositório

## FAQ

**P: Eu estava baixando vídeos normalmente, por que agora dá erro 403?**
A: YouTube pode ter detectado muitas requisições ou alterado as restrições do vídeo.

**P: Posso usar um proxy para contornar isso?**
A: Não é recomendado e viola os Termos de Serviço do YouTube.

**P: O app irá suportar videos de outras plataformas?**
A: Sim! O app também suporta Instagram. Selecione a opção no menu "Serviço".

---

**Última atualização:** 2026-08-23
