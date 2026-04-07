# Notchi for Windows

Um companheiro de área de trabalho para Windows inspirado e portado de [sk-ruban/notchi](https://github.com/sk-ruban/notchi), feito para o Claude Code.

Este repositório agora é um lançamento exclusivo para Windows. Ele mantém o mascote em pixel art original e as sprite sheets, mas adapta o aplicativo para Windows com uma pequena sobreposição sempre visível, hooks do PowerShell e escuta local de eventos.

## Visão Rápida

<p align="center">
  <img src="assets/windows-mascots.gif" alt="Mascotes animados" width="640">
</p>

Prévia animada das transições de estado `happy` (feliz), `sad` (triste), `waiting` (aguardando) e `sleeping` (dormindo).

## O Que Ele Faz

- Reage à atividade do Claude Code em tempo real
- Mostra um sprite por sessão do Claude Code
- Usa animações de sprites do Notchi incluídas, adaptadas do projeto original
- Alterna entre `idle` (ocioso), `working` (trabalhando), `waiting` (aguardando), `compacting` (compactando) e `sleeping` (dormindo)
- Alterna emoções entre `neutral` (neutro), `happy` (feliz), `sad` (triste) e `sob` (chorando)
- Permite ocultar para uma visualização compacta apenas com o mascote ou expandir em um painel de detalhes

## Status Atual

A versão para Windows é utilizável, mas ainda não é uma conversão 1:1 completa do aplicativo original para macOS.

Implementado hoje:

- Instalador de hook do Windows para o Claude Code
- Inicialização automática acionada por hook quando a atividade do Claude Code começa
- Ouvinte local de eventos TCP
- Renderização de sprites para múltiplas sessões
- Painel de detalhes com prompt recente, resposta e informações de atividade
- Alternância automática de estado e emoção
- Recursos de sprite sheets incluídos no aplicativo para Windows

Ainda não portado:

- Interface exata em formato de notch do macOS
- Atualizações automáticas no estilo Sparkle
- Paridade visual exata com o aplicativo nativo em Swift

## Executar

```powershell
git clone https://github.com/AptatoX/notchi-for-windows.git
cd notchi-for-windows/windows
python -m pip install -r ../requirements.txt
python app.py
```

Ao iniciar, o aplicativo começa em modo oculto e tenta instalar o hook do Claude Code automaticamente.

Mais notas específicas do Windows estão em [windows/README.md](windows/README.md).

## Estrutura do Projeto

- [windows/](windows/README.md): aplicativo Windows, hook e recursos de sprites incluídos
- [scripts/](scripts): scripts auxiliares para geração e limpeza de mídia no Windows

## Atribuição

Este projeto é baseado no projeto original [sk-ruban/notchi](https://github.com/sk-ruban/notchi).

Créditos aos autores originais por:

- o conceito do aplicativo
- a arte e animação dos sprites
- a implementação original para macOS e o design de interação

## Licença

MIT. Consulte também o repositório original para ver seu histórico e atribuição.
