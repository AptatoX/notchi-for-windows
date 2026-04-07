# Notchi for Windows

Esta pasta contém o lançamento de desktop do Notchi para Windows.

## Recursos

- Instala automaticamente um hook do Claude Code na inicialização
- Inicia o aplicativo automaticamente quando o Claude Code emite um evento e o Notchi ainda não está em execução
- Recebe eventos do Claude Code ao vivo através de `127.0.0.1:8765`
- Mostra um mascote animado por sessão ativa do Claude Code
- Suporta alternância automática de estado:
  - `idle` (ocioso)
  - `working` (trabalhando)
  - `waiting` (aguardando)
  - `compacting` (compactando)
  - `sleeping` (dormindo)
- Suporta alternância automática de emoção:
  - `neutral` (neutro)
  - `happy` (feliz)
  - `sad` (triste)
  - `sob` (chorando)
- Suporta modo oculto compacto e modo de detalhes expansível

## Executar

```powershell
git clone https://github.com/AptatoX/notchi-for-windows.git
cd notchi-for-windows/windows
python -m pip install -r ../requirements.txt
python app.py
```

## Interação

- Iniciar: começa em modo oculto
- Duplo clique em um mascote: alterna entre modo oculto e detalhes para aquela sessão
- Múltiplas sessões do Claude Code: cada sessão recebe seu próprio mascote

## Observações

- O aplicativo para Windows é autocontido e não depende do projeto Xcode original.
- Ele usa hooks do PowerShell e um ouvinte TCP local em vez do fluxo de socket Unix do macOS.
- As sprite sheets incluídas ficam em `windows/assets/sprites`.

## Atribuição

- Baseado em [sk-ruban/notchi](https://github.com/sk-ruban/notchi)
- Os recursos originais de sprites e o conceito permanecem creditados ao projeto original e seus autores
