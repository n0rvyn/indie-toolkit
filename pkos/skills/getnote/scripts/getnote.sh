#!/bin/bash
# Get笔记 API 封装 — 环境变量: GETNOTE_API_KEY, GETNOTE_CLIENT_ID
set -euo pipefail
BASE_URL="https://openapi.biji.com/open/api/v1"
API_KEY="${GETNOTE_API_KEY:?需要设置 GETNOTE_API_KEY}"
CLIENT_ID="${GETNOTE_CLIENT_ID:?需要设置 GETNOTE_CLIENT_ID}"

api_get() {
  local path="$1"; shift
  curl -s -X GET "${BASE_URL}${path}" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "X-Client-ID: ${CLIENT_ID}" \
    -H "Content-Type: application/json" \
    "$@"
}

api_post() {
  local path="$1"; local body="$2"; shift 2
  curl -s -X POST "${BASE_URL}${path}" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "X-Client-ID: ${CLIENT_ID}" \
    -H "Content-Type: application/json" \
    -d "$body" "$@"
}

case "${1:-}" in
  list_notes)
    # list_notes [--since-id ID]
    SINCE_ID="${2:-0}"
    api_get "/resource/note/list" --data-urlencode "since_id=${SINCE_ID}" --get
    ;;
  get_note)
    NOTE_ID="${2:-}"; IMAGE_Q="${3:-}"
    Q="id=${NOTE_ID}"
    [[ -n "$IMAGE_Q" ]] && Q+="&image_quality=${IMAGE_Q}"
    api_get "/resource/note/detail" --data-urlencode "$Q" --get
    ;;
  save_note)
    # save_note <title> <content> [tags_csv]
    TITLE="${2:-}"; CONTENT="${3:-}"; TAGS="${4:-}"
    BODY=$(python3 -c "import sys,json; d={'note_type':'plain_text','title':sys.argv[1],'content':sys.argv[2]}; print(json.dumps(d))" "$TITLE" "$CONTENT")
    [[ -n "$TAGS" ]] && BODY=$(python3 -c "import sys,json,yaml; d=json.loads(sys.argv[1]); d['tags']=sys.argv[2].split(','); print(json.dumps(d))" "$BODY" "$TAGS")
    api_post "/resource/note/save" "$BODY"
    ;;
  update_note)
    # update_note <note_id> [title] [content] [tags_csv]
    NOTE_ID="${2:-}"; TITLE="${3:-}"; CONTENT="${4:-}"; TAGS="${5:-}"
    BODY='{}'
    [[ -n "$TITLE" ]] && BODY=$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); d['note_id']=sys.argv[2]; d['title']=sys.argv[3]; print(json.dumps(d))" "$BODY" "$NOTE_ID" "$TITLE")
    [[ -n "$CONTENT" ]] && BODY=$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); d['content']=sys.argv[2]; print(json.dumps(d))" "$BODY" "$CONTENT")
    [[ -n "$TAGS" ]] && BODY=$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); d['tags']=sys.argv[2].split(','); print(json.dumps(d))" "$BODY" "$TAGS")
    api_post "/resource/note/update" "$BODY"
    ;;
  add_tags)
    # add_tags <note_id> <tags_csv>
    NOTE_ID="${2:-}"; TAGS="${3:-}"
    BODY=$(python3 -c "import sys,json; print(json.dumps({'note_id':sys.argv[1],'tags':sys.argv[2].split(',')}))" "$NOTE_ID" "$TAGS")
    api_post "/resource/note/tags/add" "$BODY"
    ;;
  delete_tag)
    # delete_tag <note_id> <tag_id>
    NOTE_ID="${2:-}"; TAG_ID="${3:-}"
    BODY=$(python3 -c "import sys,json; print(json.dumps({'note_id':sys.argv[1],'tag_id':sys.argv[2]}))" "$NOTE_ID" "$TAG_ID")
    api_post "/resource/note/tags/delete" "$BODY"
    ;;
  poll_task)
    TASK_ID="${2:-}"
    BODY=$(python3 -c "import sys,json; print(json.dumps({'task_id':sys.argv[1]}))" "$TASK_ID")
    api_post "/resource/note/task/progress" "$BODY"
    ;;
  list_topics)
    PAGE="${2:-1}"
    api_get "/resource/knowledge/list" --data-urlencode "page=${PAGE}" --get
    ;;
  list_topic_notes)
    TOPIC_ID="${2:-}"; PAGE="${3:-1}"
    api_get "/resource/knowledge/notes" --data-urlencode "topic_id=${TOPIC_ID}&page=${PAGE}" --get
    ;;
  batch_add_to_topic)
    # batch_add_to_topic <topic_id> <note_ids_csv>
    TOPIC_ID="${2:-}"; NOTE_IDS="${3:-}"
    BODY=$(python3 -c "import sys,json; print(json.dumps({'topic_id':sys.argv[1],'note_ids':sys.argv[2].split(',')}))" "$TOPIC_ID" "$NOTE_IDS")
    api_post "/resource/knowledge/note/batch-add" "$BODY"
    ;;
  recall)
    # recall <query> [top_k]
    QUERY="${2:-}"; TOP_K="${3:-3}"
    BODY=$(python3 -c "import sys,json; print(json.dumps({'query':sys.argv[1],'top_k':int(sys.argv[2])}))" "$QUERY" "$TOP_K")
    api_post "/resource/recall" "$BODY"
    ;;
  recall_knowledge)
    # recall_knowledge <topic_id> <query> [top_k]
    TOPIC_ID="${2:-}"; QUERY="${3:-}"; TOP_K="${4:-3}"
    BODY=$(python3 -c "import sys,json; print(json.dumps({'topic_id':sys.argv[1],'query':sys.argv[2],'top_k':int(sys.argv[3])}))" "$TOPIC_ID" "$QUERY" "$TOP_K")
    api_post "/resource/recall/knowledge" "$BODY"
    ;;
  list_bloggers)
    TOPIC_ID="${2:-}"; PAGE="${3:-1}"
    api_get "/resource/knowledge/bloggers" --data-urlencode "topic_id=${TOPIC_ID}&page=${PAGE}" --get
    ;;
  list_blogger_contents)
    TOPIC_ID="${2:-}"; FOLLOW_ID="${3:-}"; PAGE="${4:-1}"
    api_get "/resource/knowledge/blogger/contents" --data-urlencode "topic_id=${TOPIC_ID}&follow_id=${FOLLOW_ID}&page=${PAGE}" --get
    ;;
  blogger_content_detail)
    TOPIC_ID="${2:-}"; POST_ID="${3:-}"
    api_get "/resource/knowledge/blogger/content/detail" --data-urlencode "topic_id=${TOPIC_ID}&post_id=${POST_ID}" --get
    ;;
  list_lives)
    TOPIC_ID="${2:-}"; PAGE="${3:-1}"
    api_get "/resource/knowledge/lives" --data-urlencode "topic_id=${TOPIC_ID}&page=${PAGE}" --get
    ;;
  live_detail)
    TOPIC_ID="${2:-}"; LIVE_ID="${3:-}"
    api_get "/resource/knowledge/live/detail" --data-urlencode "topic_id=${TOPIC_ID}&live_id=${LIVE_ID}" --get
    ;;
  quota)
    api_get "/resource/rate-limit/quota"
    ;;
  *)
    echo "Get笔记 API Client" >&2
    echo "Usage: getnote.sh <command> [args...]" >&2
    exit 1
    ;;
esac
