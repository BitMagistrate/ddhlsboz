# Pitch deck

Питч-дек ЧитАИ написан в [Marp](https://marp.app) — markdown с YAML-метаданными,
рендерится в PDF/HTML локально и в CI.

## Локальный рендер

```bash
# через CLI
npx -y @marp-team/marp-cli docs/pitch/pitch.md -o docs/pitch/pitch.pdf
npx -y @marp-team/marp-cli docs/pitch/pitch.md -o docs/pitch/pitch.html

# через VSCode
# плагин: marp-team.marp-vscode
```

## Что меняется

| Файл | Что |
| --- | --- |
| `pitch.md` | Источник истины, 12 слайдов |
| `pitch.pdf` | Артефакт CI (на каждый PR, в GitHub Actions) |
| `pitch.html` | Артефакт CI (open in browser) |

При обновлении цифр бенчмарка не забудьте перерендерить
секцию «Точность поиска» (значения берутся из
`evaluation/report.json`).
