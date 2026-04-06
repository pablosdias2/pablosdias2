#!/usr/bin/env python3
"""Generate simple GitHub stats SVGs using the GitHub REST API (no external libs)."""
import os
import sys
import time
import json
import hashlib
try:
    # Python 3
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except Exception:
    print('Requires Python 3', file=sys.stderr)
    sys.exit(1)


def api_get(url, token=None):
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'github-stats-generator'
    }
    if token:
        headers['Authorization'] = f'token {token}'
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or 'utf-8'
        return json.loads(data.decode(charset))


def paginate(url, token=None):
    page = 1
    out = []
    while True:
        sep = '&' if '?' in url else '?'
        full = f"{url}{sep}per_page=100&page={page}"
        try:
            data = api_get(full, token)
        except HTTPError as e:
            raise
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.05)
    return out


def color_for_language(lang):
    colors = {
        'Python': '#3572A5', 'JavaScript': '#f1e05a', 'TypeScript': '#2b7489',
        'SQL': '#e38c00', 'HTML': '#e34c26', 'CSS': '#563d7c', 'Java': '#b07219',
        'Go': '#00ADD8', 'C++': '#f34b7d', 'C#': '#178600', 'Shell': '#89e051',
        'PHP': '#4F5D95', 'R': '#198CE7', 'Ruby': '#701516', 'Jupyter Notebook': '#DA5B0B'
    }
    if lang in colors:
        return colors[lang]
    h = hashlib.md5(lang.encode('utf-8')).hexdigest()
    return f'#{h[:6]}'


def generate_stats_svg(username, followers, total_repos, total_stars, total_forks, top_langs, outpath):
    width = 640
    height = 140
    bg = '#0b0c0f'
    fg = '#c9d1d9'
    title = f'{username} — GitHub Stats'
    if top_langs:
        langs_text = ', '.join([f'{k} ({int(v)}%)' for k, v in top_langs])
    else:
        langs_text = '—'
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="{bg}" rx="6" />
  <text x="20" y="30" fill="{fg}" font-size="18" font-family="Arial,Helvetica,sans-serif">{title}</text>
  <g transform="translate(20,45)" fill="{fg}" font-family="Arial,Helvetica,sans-serif" font-size="14">
    <text x="0" y="0">Repositórios: {total_repos}</text>
    <text x="220" y="0">Seguidores: {followers}</text>
    <text x="0" y="22">⭐ Stars: {total_stars}</text>
    <text x="220" y="22">🍴 Forks: {total_forks}</text>
    <text x="0" y="44">Linguagens: {langs_text}</text>
  </g>
</svg>
'''
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(svg)


def generate_top_langs_svg(top_langs_tuples, outpath):
    width = 420
    height = 140
    bg = '#0b0c0f'
    fg = '#c9d1d9'
    padding = 12
    bar_x = 140
    max_bar_w = width - bar_x - padding
    header = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="{bg}" rx="6" />
  <text x="{padding}" y="20" fill="{fg}" font-size="16" font-family="Arial,Helvetica,sans-serif">Top Languages</text>
'''
    rows = ''
    y_start = 40
    for i, (lang, percent) in enumerate(top_langs_tuples):
        y = y_start + i * 24
        bar_w = int((percent / 100.0) * max_bar_w) if percent > 0 else 0
        color = color_for_language(lang)
        rows += f'  <text x="{padding}" y="{y+12}" fill="{fg}" font-size="12" font-family="Arial,Helvetica,sans-serif">{lang}</text>\n'
        rows += f'  <rect x="{bar_x}" y="{y}" width="{bar_w}" height="16" rx="4" fill="{color}" />\n'
        rows += f'  <text x="{bar_x+bar_w+6}" y="{y+12}" fill="{fg}" font-size="12" font-family="Arial,Helvetica,sans-serif">{int(percent)}%</text>\n'
    footer = '</svg>'
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(header + rows + footer)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--outdir', default='assets')
    args = parser.parse_args()
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    username = args.username
    try:
        user = api_get(f'https://api.github.com/users/{username}', token)
    except Exception as e:
        print('Erro ao buscar usuário:', e, file=sys.stderr)
        sys.exit(1)
    followers = user.get('followers', 0)
    total_repos = user.get('public_repos', 0)
    try:
        repos = paginate(f'https://api.github.com/users/{username}/repos', token)
    except Exception:
        repos = []
    total_stars = sum(r.get('stargazers_count', 0) for r in repos)
    total_forks = sum(r.get('forks_count', 0) for r in repos)
    lang_map = {}
    for r in repos:
        lang_url = r.get('languages_url')
        if not lang_url:
            continue
        try:
            langs = api_get(lang_url, token)
        except Exception:
            continue
        for k, v in langs.items():
            lang_map[k] = lang_map.get(k, 0) + v
    if lang_map:
        total_bytes = sum(lang_map.values())
        top = sorted(lang_map.items(), key=lambda x: x[1], reverse=True)[:6]
        top_percent = [(k, v * 100.0 / total_bytes) for k, v in top]
    else:
        top_percent = []
    os.makedirs(args.outdir, exist_ok=True)
    github_stats_path = os.path.join(args.outdir, 'github-stats.svg')
    top_langs_path = os.path.join(args.outdir, 'top-langs.svg')
    generate_stats_svg(username, followers, total_repos, total_stars, total_forks, [(k, round(p)) for k, p in top_percent], github_stats_path)
    generate_top_langs_svg([(k, p) for k, p in top_percent], top_langs_path)
    print('Generated:', github_stats_path, top_langs_path)


if __name__ == '__main__':
    main()
