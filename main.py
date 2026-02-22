import os
import json
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime
import time

app = FastAPI()

# Railway akan otomatis mengisi env ini dari PostgreSQL Addon
PGHOST = os.environ.get("PGHOST", "")
PGPORT = os.environ.get("PGPORT", "")
PGUSER = os.environ.get("PGUSER", "")
PGPASSWORD = os.environ.get("PGPASSWORD", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "")

# Connection Pool
db_pool = pool.SimpleConnectionPool(
    1, 20,
    dbname=POSTGRES_DB,
    user=PGUSER,
    password=PGPASSWORD,
    host=PGHOST,
    port=PGPORT
)

def get_db():
    return db_pool.getconn()

def put_db(conn):
    db_pool.putconn(conn)

# RAM Cache
cache_data = None
cache_time = 0
CACHE_TTL = 1  # detik

def get_request():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT data FROM request ORDER BY updated_at DESC LIMIT 1")
    row = c.fetchone()
    c.close()
    put_db(conn)
    if row:
        return row[0]
    return None

@app.get("/", response_class=HTMLResponse)
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ranking Chat Indodax</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
        <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 30px; }
            table.dataTable thead th { font-weight: bold; }
            .btn-history { display:inline-block; margin-bottom:20px; padding:8px 16px; background:#00abff; color:#fff; border:none; border-radius:4px; text-decoration:none;}
            .btn-history:hover { background:#0056b3; }
            .cusername {
                color: #A0B6C8;
                font-weight: bold;
                cursor: pointer;
            }
            .level-0 { color: #5E5E5E; }
            .level-1 { color: #5B2D00; }
            .level-2 { color: #FF8200; text-shadow: 1px 1px #CCCCCC; }
            .level-3 { color: #034AC4; text-shadow: 1px 1px #CCCCCC; }
            .level-4 { color: #00E124; text-shadow: 1px 1px #00B31C; }
            .level-5 { color: #B232B2 }
            th, td {
                vertical-align: top;
            }
            th:nth-child(1), td:nth-child(1) { width: 10px; min-width: 10px; max-width: 20px; white-space: nowrap; }
            th:nth-child(2), td:nth-child(2) { width: 120px; min-width: 90px; max-width: 150px; white-space: nowrap; }
            th:nth-child(3), td:nth-child(3) { width: 10px; min-width: 10px; max-width: 35px; white-space: nowrap; }
            th:nth-child(4), td:nth-child(4) { width: auto; word-break: break-word; white-space: pre-line; }
            th:nth-child(5), td:nth-child(5) { width: 130px; min-width: 110px; max-width: 150px; white-space: nowrap; }

            /* Modal Styles */
            .modal-overlay {
                display: none;
                position: fixed;
                top: 0; left: 0;
                width: 100%; height: 100%;
                background: rgba(0,0,0,0.6);
                z-index: 9999;
                justify-content: center;
                align-items: center;
            }
            .modal-overlay.active {
                display: flex;
            }
            .modal-box {
                background: #fff;
                border-radius: 10px;
                width: 90%;
                max-width: 900px;
                max-height: 85vh;
                display: flex;
                flex-direction: column;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 24px;
                background: #00abff;
                color: #fff;
            }
            .modal-header h3 {
                margin: 0;
                font-size: 18px;
            }
            .modal-close {
                background: none;
                border: none;
                color: #fff;
                font-size: 28px;
                cursor: pointer;
                font-weight: bold;
                line-height: 1;
            }
            .modal-close:hover {
                color: #ff4444;
            }
            .modal-body {
                padding: 20px 24px;
                overflow-y: auto;
                flex: 1;
            }
            .modal-body table {
                width: 100%;
            }
            .modal-body th:nth-child(1), .modal-body td:nth-child(1) {
                width: 10px; min-width: 10px; max-width: 20px; white-space: nowrap;
            }
            .modal-body th:nth-child(2), .modal-body td:nth-child(2) {
                width: 130px; min-width: 110px; max-width: 160px; white-space: nowrap;
            }
            .modal-body th:nth-child(3), .modal-body td:nth-child(3) {
                width: 100px; min-width: 80px; max-width: 150px; white-space: nowrap;
            }
            .modal-body th:nth-child(4), .modal-body td:nth-child(4) {
                width: auto; word-break: break-word; white-space: pre-line;
            }
            .modal-loading {
                text-align: center;
                padding: 40px;
                color: #888;
                font-size: 16px;
            }
            .chat-total-info {
                margin-bottom: 12px;
                font-size: 14px;
                color: #555;
            }
        </style>
    </head>
    <body>
    <h2>Top Chatroom Indodax</h2>
    <a href="https://cr-indodax.up.railway.app/" class="btn-history">Chat Terkini</a>
    <table id="ranking" class="display" style="width:100%">
        <thead>
        <tr>
            <th>No</th>
            <th>Username</th>
            <th>Total</th>
            <th>Terakhir Chat</th>
            <th>Waktu Chat</th>
        </tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <p id="periode"></p>

    <!-- Modal Detail Chat -->
    <div class="modal-overlay" id="chatModal">
        <div class="modal-box">
            <div class="modal-header">
                <h3 id="modalTitle">Chat dari: -</h3>
                <button class="modal-close" id="modalClose">&times;</button>
            </div>
            <div class="modal-body">
                <div class="chat-total-info" id="chatTotalInfo"></div>
                <table id="chatDetail" class="display" style="width:100%">
                    <thead>
                    <tr>
                        <th>No</th>
                        <th>Waktu</th>
                        <th>Username</th>
                        <th>Isi Chat</th>
                    </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        var table = $('#ranking').DataTable({
            "order": [[2, "desc"]],
            "paging": false,
            "info": false,
            "searching": true,
            "language": {
                "emptyTable": "Tidak ada DATA"
            }
        });

        var chatTable = null;

        function initChatTable() {
            if (chatTable) {
                chatTable.destroy();
                $('#chatDetail tbody').empty();
            }
            chatTable = $('#chatDetail').DataTable({
                "order": [[1, "desc"]],
                "paging": true,
                "pageLength": 50,
                "info": true,
                "searching": true,
                "language": {
                    "emptyTable": "Tidak ada chat ditemukan",
                    "info": "Menampilkan _START_ - _END_ dari _TOTAL_ chat",
                    "paginate": { "previous": "Prev", "next": "Next" }
                }
            });
        }

        function openChatModal(username) {
            $('#chatModal').addClass('active');
            $('#modalTitle').text('Chat dari: ' + username);
            $('#chatTotalInfo').html('<span class="modal-loading">Memuat data chat...</span>');

            if (chatTable) {
                chatTable.destroy();
                $('#chatDetail tbody').empty();
            }

            $.getJSON("/chat_detail?username=" + encodeURIComponent(username), function(data) {
                initChatTable();
                chatTable.clear();

                if (data.chats.length === 0) {
                    $('#chatTotalInfo').html('Total chat: <b>0</b>');
                    chatTable.draw();
                    return;
                }

                $('#chatTotalInfo').html('Total chat: <b>' + data.chats.length + '</b> | Periode: <b>' + data.t_awal + '</b> s/d <b>' + data.t_akhir + '</b>');

                for (var i = 0; i < data.chats.length; i++) {
                    var chat = data.chats[i];
                    chatTable.row.add([
                        i + 1,
                        chat.timestamp,
                        '<span class="level-' + chat.level + ' cusername">' + chat.username + '</span>',
                        '<span class="level-' + chat.level + '">' + chat.content + '</span>'
                    ]);
                }
                chatTable.draw();
            }).fail(function() {
                $('#chatTotalInfo').html('<span style="color:red;">Gagal memuat data chat</span>');
            });
        }

        // Close modal
        $('#modalClose').click(function() {
            $('#chatModal').removeClass('active');
        });
        $('#chatModal').click(function(e) {
            if (e.target === this) {
                $(this).removeClass('active');
            }
        });
        $(document).keydown(function(e) {
            if (e.key === "Escape") {
                $('#chatModal').removeClass('active');
            }
        });

        // Klik username di tabel ranking
        $(document).on('click', '#ranking tbody .cusername', function() {
            var username = $(this).text().trim();
            openChatModal(username);
        });

        function loadData() {
            $.getJSON("/data", function(data) {
                table.clear();
                if (data.ranking.length === 0) {
                    $("#periode").html("<b>Tidak ada DATA</b>");
                    table.draw();
                    return;
                }
                for (var i = 0; i < data.ranking.length; i++) {
                    var row = data.ranking[i];
                    table.row.add([
                        i+1,
                        '<span class="level-' + row.level + ' cusername">' + row.username + '</span>',
                        row.count,
                        '<span class="level-' + row.level + ' cusername">' + row.last_content + '</span>',
                        row.last_time
                    ]);
                }
                table.draw();
                $("#periode").html("Periode: <b>" + data.t_awal + "</b> s/d <b>" + data.t_akhir + "</b>");
            });
        }

        loadData();
        setInterval(loadData, 1000);
    </script>
    </body>
    </html>
    """
    return html

@app.get("/data")
def data():
    global cache_data, cache_time
    now = time.time()
    if cache_data and now - cache_time < CACHE_TTL:
        return cache_data

    req = get_request()
    if not req:
        result = {"ranking": [], "t_awal": "-", "t_akhir": "-"}
        cache_data = result
        cache_time = now
        return result

    t_awal = req.get("start", "-")
    t_akhir = req.get("end", "-")
    usernames = [u.lower() for u in req.get("usernames", [])]
    usernames_filter = [u.lower() for u in req.get("usernames", [])]
    mode = req.get("mode", "")
    kata = req.get("kata", None)
    level = req.get("level", None)

    conn = get_db()
    c = conn.cursor()
    query = "SELECT username, content, timestamp_wib, level FROM chat WHERE timestamp_wib >= %s AND timestamp_wib <= %s"
    params = [t_awal, t_akhir]
    if kata:
        query += " AND LOWER(content) LIKE %s"
        params.append(f"%{kata}%")
    if mode == "username" and usernames:
        query += " AND LOWER(username) = ANY(%s)"
        params.append(usernames)
    if mode == "level" and level is not None:
        query += " AND level = %s"
        params.append(level)
    c.execute(query, params)
    rows = c.fetchall()
    c.close()
    put_db(conn)

    user_info = {}
    for row in rows:
        uname = row[0]
        uname_lower = uname.lower()
        content = row[1]
        t_chat = row[2]
        level = row[3]
        if uname_lower not in user_info:
            user_info[uname_lower] = {
                "username": uname,
                "count": 1,
                "last_content": content,
                "last_time": t_chat,
                "level": level
            }
        else:
            user_info[uname_lower]["count"] += 1
            if t_chat > user_info[uname_lower]["last_time"]:
                user_info[uname_lower]["last_content"] = content
                user_info[uname_lower]["last_time"] = t_chat
                user_info[uname_lower]["level"] = level

    if mode == "username" and usernames:
        ranking = []
        for u in usernames_filter:
            if u in user_info:
                ranking.append((user_info[u]["username"], user_info[u]))
            else:
                ranking.append((u, {"username": u, "count": 0, "last_content": "-", "last_time": "-", "level": 0}))
        ranking = sorted(
            ranking,
            key=lambda x: (-x[1]["count"], x[1]["last_time"])
        )
    else:
        ranking = sorted(
            [(info["username"], info) for info in user_info.values()],
            key=lambda x: (-x[1]["count"], x[1]["last_time"])
        )

    data_result = []
    for user, info in ranking:
        data_result.append({
            "username": user,
            "count": info["count"],
            "last_content": info["last_content"],
            "last_time": info["last_time"],
            "level": info.get("level", 0)
        })
    result = {
        "ranking": data_result,
        "t_awal": t_awal,
        "t_akhir": t_akhir
    }
    cache_data = result
    cache_time = now
    return result


@app.get("/chat_detail")
def chat_detail(username: str):
    """Endpoint untuk mengambil detail chat dari username tertentu"""
    req = get_request()
    if not req:
        return {"chats": [], "t_awal": "-", "t_akhir": "-"}

    t_awal = req.get("start", "-")
    t_akhir = req.get("end", "-")
    kata = req.get("kata", None)

    conn = get_db()
    c = conn.cursor()
    query = """
        SELECT username, content, timestamp_wib, level 
        FROM chat 
        WHERE timestamp_wib >= %s AND timestamp_wib <= %s 
        AND LOWER(username) = LOWER(%s)
    """
    params = [t_awal, t_akhir, username]

    if kata:
        query += " AND LOWER(content) LIKE %s"
        params.append(f"%{kata}%")

    query += " ORDER BY timestamp_wib DESC"

    c.execute(query, params)
    rows = c.fetchall()
    c.close()
    put_db(conn)

    chats = []
    for row in rows:
        chats.append({
            "username": row[0],
            "content": row[1],
            "timestamp": row[2],
            "level": row[3]
        })

    return {
        "chats": chats,
        "t_awal": t_awal,
        "t_akhir": t_akhir
    }
