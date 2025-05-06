import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import csv
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ARQUIVO = "gastos.csv"
CONFIRMACAO_LIMPEZA = {}

# Grava a compra
def registrar_compra(texto):
    partes = texto.split(" - ")
    if len(partes) < 3:
        return "❌ Formato inválido. Use:\nDescrição - R$Valor - Categoria - Cartão - Pessoa (os dois últimos são opcionais)"

    descricao = partes[0]
    valor_str = partes[1].lower().replace("r$", "").replace(",", ".").strip()

    try:
        valor = float(valor_str)
    except ValueError:
        return f"❌ Valor inválido: {valor_str}"

    categoria = partes[2]
    cartao = partes[3] if len(partes) >= 4 else "Desconhecido"
    pessoa = partes[4] if len(partes) == 5 else "Desconhecido"
    data = datetime.now().strftime("%Y-%m-%d")

    with open(ARQUIVO, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([data, descricao, categoria, valor, cartao, pessoa])

    return f"✅ Compra registrada: {descricao} - R${valor:.2f} ({categoria}, {cartao}, {pessoa})"

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Envie compras no formato:\nDescrição - R$Valor - Categoria - Cartão - Pessoa\n\nExemplo:\nSupermercado - R$120,50 - Alimentação - Nubank - Wendell\n\nUse /relatorio ou /ajuda para mais comandos."
    )

# Comando /ajuda
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await comandos(update, context)

# Comando /comandos ou /ajuda
async def comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "📚 Comandos disponíveis:\n\n"
        "/start – Mensagem de boas-vindas\n"
        "/ajuda – Mostra esta lista de comandos\n"
        "/relatorio – Mostra relatório geral\n"
        "/relatorio MM AAAA – Relatório por mês\n"
        "/relatorio 01 05 2025 a 30 05 2025 – Por período\n"
        "/relatorio MM AAAA Cartão – Filtra por cartão\n"
        "/relatorio MM AAAA Cartão Pessoa – Filtra por cartão e pessoa\n"
        "/relatorio Pessoa – Filtra por nome da pessoa\n"
        "/limpar – Apaga todos os registros (com confirmação)\n"
    )
    await update.message.reply_text(texto)

# Comando /relatorio
async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    filtro_inicio = None
    filtro_fim = None
    filtro_cartao = None
    filtro_pessoa = None

    try:
        # /relatorio 01 05 2025 a 30 05 2025
        if len(args) >= 7 and args[3].lower() == "a":
            dia_i, mes_i, ano_i = map(int, args[0:3])
            dia_f, mes_f, ano_f = map(int, args[4:7])
            filtro_inicio = datetime(ano_i, mes_i, dia_i)
            filtro_fim = datetime(ano_f, mes_f, dia_f)
            if len(args) >= 8:
                filtro_cartao = args[7].lower()
            if len(args) == 9:
                filtro_pessoa = args[8].lower()
        # /relatorio MM AAAA [Cartão] [Pessoa]
        elif len(args) >= 2 and args[0].isdigit():
            mes, ano = int(args[0]), int(args[1])
            filtro_inicio = datetime(ano, mes, 1)
            if mes == 12:
                filtro_fim = datetime(ano + 1, 1, 1)
            else:
                filtro_fim = datetime(ano, mes + 1, 1)
            if len(args) >= 3:
                filtro_cartao = args[2].lower()
            if len(args) == 4:
                filtro_pessoa = args[3].lower()
        # /relatorio NomePessoa
        elif len(args) == 1:
            filtro_pessoa = args[0].lower()
    except ValueError:
        await update.message.reply_text("❌ Formato inválido. Use:\n/relatorio 01 05 2025 a 30 05 2025\nou\n/relatorio 05 2025 [Cartão] [Pessoa]")
        return

    total = 0
    categorias = {}

    try:
        with open(ARQUIVO, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 6:
                    data_str, desc, cat, val, cartao, pessoa = row
                elif len(row) == 5:
                    data_str, desc, cat, val, cartao = row
                    pessoa = "Desconhecido"
                elif len(row) == 4:
                    data_str, desc, cat, val = row
                    cartao = "Desconhecido"
                    pessoa = "Desconhecido"
                else:
                    continue

                try:
                    val = float(val)
                    data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                except:
                    continue

                if filtro_inicio and filtro_fim:
                    if not (filtro_inicio <= data_obj <= filtro_fim):
                        continue
                if filtro_cartao and cartao.lower() != filtro_cartao:
                    continue
                if filtro_pessoa and pessoa.lower() != filtro_pessoa:
                    continue

                total += val
                categorias[cat] = categorias.get(cat, 0) + val

        if total == 0:
            await update.message.reply_text("Nenhum gasto encontrado nesse filtro.")
            return

        cabecalho = "📊 Relatório"
        if filtro_inicio and filtro_fim:
            cabecalho += f" de {filtro_inicio.strftime('%d/%m/%Y')} a {filtro_fim.strftime('%d/%m/%Y')}"
        if filtro_cartao:
            cabecalho += f" | Cartão: {filtro_cartao.capitalize()}"
        if filtro_pessoa:
            cabecalho += f" | Pessoa: {filtro_pessoa.capitalize()}"

        resumo = f"{cabecalho}\nTotal: R${total:.2f}"
        for cat, val in categorias.items():
            resumo += f"\n- {cat}: R${val:.2f}"

        await update.message.reply_text(resumo)

    except FileNotFoundError:
        await update.message.reply_text("Nenhuma compra registrada ainda.")

# Comando /limpar
async def limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    CONFIRMACAO_LIMPEZA[user_id] = True
    await update.message.reply_text("⚠️ Tem certeza que deseja apagar todos os dados?\nDigite CONFIRMAR para continuar.")

# Trata mensagens gerais
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    user_id = update.message.from_user.id

    if texto.upper() == "CONFIRMAR" and CONFIRMACAO_LIMPEZA.get(user_id):
        try:
            open(ARQUIVO, "w", encoding="utf-8").close()
            await update.message.reply_text("🧹 Limpeza concluída! Todos os dados foram apagados.")
        except:
            await update.message.reply_text("❌ Erro ao tentar apagar os dados.")
        CONFIRMACAO_LIMPEZA[user_id] = False
        return

    resposta = registrar_compra(texto)
    await update.message.reply_text(resposta)

# Executa o bot
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("❌ BOT_TOKEN não definido no .env")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("comandos", comandos))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("limpar", limpar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot rodando... Envie mensagens no Telegram.")
    app.run_polling()

if __name__ == "__main__":
    main()
