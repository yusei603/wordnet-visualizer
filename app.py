from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)  # CORS有効化

DB_PATH = 'wnjpn.db'  # SQLiteデータベースパス

def get_synonym_graph(word):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 検索語の単語ID取得
    cur.execute("SELECT wordid FROM word WHERE lemma=?", (word,))
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return {}

    # synsetと品詞のリスト取得（名詞、動詞のみ）
    synsets = []
    for (wordid,) in rows:
        cur.execute("SELECT synset FROM sense WHERE wordid=?", (wordid,))
        for (synset,) in cur.fetchall():
            # synsetテーブルでposを取得
            cur.execute("SELECT pos FROM synset WHERE synset=?", (synset,))
            row = cur.fetchone()
            if row:
                pos = row[0]
                if pos in ('n', 'v'):
                    synsets.append((synset, pos))

    graph = {"nodes": [], "links": []}

    # 検索単語ノード（灰色）
    graph["nodes"].append({
        "id": word,
        "label": word,
        "group": 0,
        "color": "#9e9e9e"  # 灰色
    })

    pos_added = set()
    for synset, pos in synsets:
        pos_label = "名詞" if pos == 'n' else "動詞"
        pos_node_id = f"{word}_{pos}"
        color = "#42a5f5" if pos == 'n' else "#ef5350"

        # 品詞ノード（1つだけ追加）
        if pos_node_id not in pos_added:
            graph["nodes"].append({
                "id": pos_node_id,
                "label": pos_label,
                "group": 1,
                "color": color
            })
            graph["links"].append({"source": word, "target": pos_node_id})
            pos_added.add(pos_node_id)

        # 日本語定義ノード（同色）
        cur.execute(
            "SELECT def FROM synset_def WHERE synset=? AND lang='jpn'", (synset,)
        )
        row = cur.fetchone()
        definition = row[0] if row else ""
        def_node_id = f"{synset}_def"
        graph["nodes"].append({
            "id": def_node_id,
            "label": definition,
            "group": 2,
            "color": color
        })
        graph["links"].append({"source": pos_node_id, "target": def_node_id})

        # 同義語ノード（緑）、検索単語除外
        cur.execute(
            "SELECT w.lemma FROM word w JOIN sense s ON w.wordid=s.wordid "
            "WHERE s.synset=? AND w.lang='eng'", (synset,)
        )
        for (syn_word,) in cur.fetchall():
            if syn_word == word:
                continue
            syn_id = f"{syn_word}_{synset}"
            graph["nodes"].append({
                "id": syn_id,
                "label": syn_word,
                "group": 3,
                "color": "#8bc34a"  # 緑
            })
            graph["links"].append({"source": def_node_id, "target": syn_id})

    conn.close()
    return graph

@app.route('/api/related')
def related():
    word = request.args.get('word', '').strip().lower()
    if not word:
        return jsonify({"error": "No word provided"}), 400
    try:
        return jsonify(get_synonym_graph(word))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

