#!/usr/bin/env python3
"""
Get笔记 JSON 解析辅助脚本
用于处理 getnote.sh 输出的 JSON 数据
"""
import sys
import json


def filter_notes_by_tag(notes_json, exclude_tag):
    """过滤掉包含指定 tag 的笔记"""
    data = json.loads(notes_json)
    filtered = []
    for note in data.get('notes', []):
        tag_names = [t.get('name', '') for t in note.get('tags', [])]
        if exclude_tag not in tag_names:
            filtered.append(note)
    return filtered


def format_note_summary(note):
    """格式化笔记摘要"""
    return {
        'id': note.get('id'),
        'title': note.get('title', 'Untitled'),
        'note_type': note.get('note_type', 'plain_text'),
        'tags': [t.get('name') for t in note.get('tags', []) if t.get('name')],
        'updated_at': note.get('updated_at', ''),
    }


def parse_recall_results(recall_json, include_external=False):
    """解析 recall 结果，可选过滤外部类型"""
    data = json.loads(recall_json)
    results = data.get('results', [])
    if not include_external:
        results = [r for r in results if r.get('note_type') in ('NOTE', 'FILE')]
    return results


if __name__ == '__main__':
    # CLI interface for common operations
    if len(sys.argv) < 2:
        print("Usage: getnote.py <command> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'filter-untagged':
        # filter-untagged <exclude_tag>
        exclude_tag = sys.argv[2] if len(sys.argv) > 2 else 'pkos-synced'
        input_json = sys.stdin.read()
        filtered = filter_notes_by_tag(input_json, exclude_tag)
        for note in filtered:
            print(f"{note['id']}\t{note.get('title','Untitled')}\t{note.get('note_type','plain_text')}")

    elif cmd == 'summarize-notes':
        # summarize-notes
        input_json = sys.stdin.read()
        data = json.loads(input_json)
        for note in data.get('notes', []):
            summary = format_note_summary(note)
            print(json.dumps(summary))

    elif cmd == 'filter-recall':
        # filter-recall [--include-external]
        include_external = '--include-external' in sys.argv
        input_json = sys.stdin.read()
        results = parse_recall_results(input_json, include_external)
        print(json.dumps({'results': results}))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
