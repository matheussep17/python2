# Solução de Problemas - Downloads do YouTube

## Erros Comuns e Soluções

### 1. **Erro: "No supported JavaScript runtime could be found"**

O YouTube exige um JavaScript runtime para extrair informações atualizadas. A aplicação tenta usar `Node.js` por padrão.

**Solução:**
1. Instale o Node.js de: https://nodejs.org
2. Escolha a versão LTS (recomendado)
3. Durante a instalação, ative "Add to PATH"
4. Reinicie a aplicação

**Verificação:** Abra PowerShell/CMD e execute:
```powershell
node --version
```

Se retornar uma versão (ex: `v18.17.0`), está instalado corretamente.

---

### 2. **Erro: "HTTP Error 429: Too Many Requests"**

YouTube limitou suas requisições. Isso é temporário e normalmente dura alguns minutos.

**Soluções:**
- ✅ **Aguarde 5-15 minutos** antes de tentar novamente
- ✅ **Use URLs diferentes** - se estiver baixando muitos vídeos, espaçe os downloads
- ✅ **Reinicie a navegação** - limpe cache do navegador e cookies
- ❌ Não use VPN/Proxy no YouTube (aumenta suspeita)

**Se continuar após muito tempo:**
1. Atualize o yt-dlp:
```bash
pip install --upgrade yt-dlp
```

2. Reinicie o Windows (limpa conexões em cache)

---

### 3. **Erro: "Sign in to confirm you're not a bot"**

YouTube detectou comportamento automatizado e pediu verificação.

**Soluções:**
- ✅ **Aguarde 1-2 horas** antes de tentar novamente
- ✅ **Faça login no navegador** - entre no YouTube normalmente em https://youtube.com
- ✅ **Verifique a conta** se solicitado
- ✅ **Tente outro vídeo**, preferencialmente com acesso público

**Para vídeos privados/restritos:**
Se o vídeo requer login, a aplicação não consegue baixar. Esse é um comportamento esperado do YouTube.

---

## Configurações Aplicadas para Melhorar Estabilidade

A aplicação foi atualizada com:

| Configuração | Função |
|--------------|--------|
| `socket_timeout: 60` | Aguarde até 60s por resposta do servidor |
| `retries: 5` | Tenta 5 vezes se houver erro de conexão |
| `fragment_retries: 5` | Tenta 5 vezes por fragmento de vídeo |
| `skip_unavailable_fragments: True` | Pula fragmentos indisponíveis |
| `extractor_sleep_json: {"youtube": 2}` | Aguarda 2s entre requisições |

Essas configurações reduzem problemas de rate limiting e timeouts.

---

## Checklist de Diagnóstico

Se ainda tiver problemas, verifique:

- [ ] Node.js instalado: `node --version`
- [ ] yt-dlp atualizado: `pip install --upgrade yt-dlp`
- [ ] FFmpeg disponível (verifique em Compressor se está ok)
- [ ] Conexão de internet estável
- [ ] URL do vídeo é válida e pública
- [ ] Não está usando VPN
- [ ] Aguardou tempo suficiente após erro 429

---

## Contato / Mais Ajuda

Se o problema persistir:
1. Atualize a aplicação para a versão mais recente
2. Tente em outro computador/rede
3. Verifique https://github.com/yt-dlp/yt-dlp/issues para problemas conhecidos

---

**Última atualização:** 31 de março de 2026
