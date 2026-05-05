"""
Conversor Missa -> Holyrics  (Web App)
======================================
Servidor Flask que converte PDFs do folheto (Versão Celular) em TXT
prontos para o Holyrics, dividindo em Parte 1 (até a Homilia) e Parte 2.

Endpoints:
  GET  /             página principal (HTML mobile-first)
  POST /converter    recebe um PDF (multipart) e devolve um JSON com os
                     dois TXTs (text e text2) e nomes sugeridos
"""

from __future__ import annotations
import io
import re
import sys
import tempfile
import traceback
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

# Importa o conversor
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))  # caso esteja na pasta superior

import converter_missa_holyrics as conv  # noqa: E402


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/saude")
def saude():
    return jsonify({"ok": True})


def _slug(nome: str) -> str:
    """Limpa o nome de arquivo para uso em downloads."""
    nome = re.sub(r"_CELULAR|\s-\sCELULAR", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\.pdf$", "", nome, flags=re.IGNORECASE)
    return nome.strip()


@app.route("/converter", methods=["POST"])
def converter():
    if "pdf" not in request.files:
        return jsonify({"erro": "Nenhum arquivo PDF enviado."}), 400

    arquivo = request.files["pdf"]
    if not arquivo.filename:
        return jsonify({"erro": "Arquivo sem nome."}), 400

    if not arquivo.filename.lower().endswith(".pdf"):
        return jsonify({"erro": "Envie um arquivo .pdf."}), 400

    base = _slug(Path(arquivo.filename).stem)

    # Salva temporariamente
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        pdf_path = td_path / "entrada.pdf"
        arquivo.save(pdf_path)

        try:
            saida_dir = td_path / "saida"
            p1, p2 = conv.converter(pdf_path, saida_dir)
            txt1 = p1.read_text(encoding="utf-8")
            txt2 = p2.read_text(encoding="utf-8")
        except Exception as e:
            tb = traceback.format_exc()
            print("ERRO na conversão:\n", tb, file=sys.stderr)
            return jsonify({
                "erro": "Falha ao converter o PDF.",
                "detalhe": str(e),
            }), 500

    return jsonify({
        "ok": True,
        "base": base,
        "parte1": {
            "nome": f"{base} - Parte 1.txt",
            "conteudo": txt1,
            "tamanho": len(txt1),
        },
        "parte2": {
            "nome": f"{base} - Parte 2.txt",
            "conteudo": txt2,
            "tamanho": len(txt2),
        },
    })


@app.route("/baixar", methods=["POST"])
def baixar():
    """Devolve o conteúdo como arquivo para forçar download (mobile)."""
    nome = request.form.get("nome", "arquivo.txt")
    conteudo = request.form.get("conteudo", "")
    buf = io.BytesIO(conteudo.encode("utf-8"))
    return send_file(
        buf,
        as_attachment=True,
        download_name=nome,
        mimetype="text/plain; charset=utf-8",
    )


if __name__ == "__main__":
    import os
    porta = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=porta, debug=False)
