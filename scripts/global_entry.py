"""Maintain one Codex knowledge-base pointer; stdlib only, dry run by default."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

BEGIN = '<!-- ai-knowledge-base:begin -->'
END = '<!-- ai-knowledge-base:end -->'

def render(root):
    return f'''{BEGIN}
## 个人知识库入口
固定知识库：`{root.as_posix()}`。
- 涉及本人、目标、决定或已有项目时，先读该库 AGENTS.md、现在看这里.md 和 02-资产，再按需读对应项目主记录；无关任务不读取个人资料。
- 已确认的结论、稿子和决定当场写回该库对应文件，标日期；采访搭建先等总结确认。记住、丢进灵感库、清理、体检均定位此库，不在当前项目新建第二套。
- 入口失效或无法访问时报告并核对路径，停止写入，不默默新建替代库、不扩大权限。
- 保留当前项目规则和权限边界，不自动上传个人资料；其他机器、云端和其他 AI 不会因此自动同步。
{END}'''

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True)
    ap.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    root = Path(args.root).expanduser()
    home = Path(args.codex_home).expanduser()
    if not root.is_absolute() or not home.is_absolute():
        ap.error('root and codex-home must be absolute')
    root = root.resolve(); home = home.resolve()
    if any(c in root.as_posix() for c in '\r\n`'):
        ap.error('root contains unsupported newline or backtick')
    if not all((root/f).is_file() for f in ('AGENTS.md','现在看这里.md')):
        ap.error('knowledge-base entry files missing; do not create a replacement vault')
    for f in ('AGENTS.md','现在看这里.md'):
        (root/f).read_text(encoding='utf-8-sig')
    normal = home/'AGENTS.md'; override = home/'AGENTS.override.md'
    contents = {f: f.read_bytes() if f.exists() else b'' for f in (normal,override)}
    decoded = {f: v.decode('utf-8-sig') for f,v in contents.items()}
    target = override if decoded[override].strip() else normal
    marked = [f for f,s in decoded.items() if BEGIN in s or END in s]
    if any(f != target for f in marked):
        ap.error('managed entry in inactive file; reconcile before editing')
    s = decoded[target]
    if s.count(BEGIN) != s.count(END) or s.count(BEGIN)>1 or (BEGIN in s and s.index(BEGIN)>s.index(END)):
        ap.error('ambiguous or damaged managed markers')
    raw = contents[target]
    newline = b'\r\n' if b'\r\n' in raw else b'\n'
    block = render(root).replace('\n',newline.decode()).encode('utf-8')
    if BEGIN in s:
        start = raw.index(BEGIN.encode()); end = raw.index(END.encode())+len(END)
        old = raw[start:end].decode('utf-8')
        # Changing an existing root needs explicit reconciliation, not a silent retarget.
        expected = f'固定知识库：`{root.as_posix()}`。'
        if expected not in old:
            ap.error('existing managed entry points elsewhere; reconcile explicitly')
        result = raw[:start]+block+raw[end:]
    else:
        result = raw+(b'' if not raw or raw.endswith(newline*2) else newline if raw.endswith(newline) else newline*2)+block+newline
    changed = result != raw
    backup = None
    if args.apply and changed:
        home.mkdir(parents=True,exist_ok=True)
        if raw:
            backup = target.with_name(target.name+'.kb-backup-'+hashlib.sha256(raw).hexdigest()[:12])
            if backup.exists() and backup.read_bytes()!=raw:
                raise RuntimeError('backup collision')
            if not backup.exists(): backup.write_bytes(raw)
        if (target.read_bytes() if target.exists() else b'') != raw:
            raise RuntimeError('instructions changed concurrently; reread and retry')
        fd,tmp = tempfile.mkstemp(dir=home,prefix='.kb-entry-')
        try:
            with os.fdopen(fd,'wb') as stream: stream.write(result)
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    print(json.dumps({'target':str(target),'root':str(root),'changed':changed,'applied':bool(args.apply and changed),'backup':str(backup) if backup else None,'entry':render(root)},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
