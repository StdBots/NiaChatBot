import html
import os
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from app.config.settings import OWNER_ID, UPSTREAM_REPO, GIT_TOKEN
from app.services.helpers import SUDO_USERS, get_mention, resolve_target, format_money, reload_sudoers
from app.database.mongo import users_col as users_collection, sudo_col as sudoers_collection, groups_col as groups_collection


# ==============================
# 🔐 SUDO HELP
# ==============================

async def sudo_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUDO_USERS:
        return

    msg = (
        "🔐 <b>Sudo Panel</b>\n\n"
        "<b>💰 Economy:</b>\n"
        "‣ /addcoins [amt] [user]\n"
        "‣ /rmcoins [amt] [user]\n"
        "‣ /freerevive [user]\n"
        "‣ /unprotect [user]\n\n"
        "<b>📢 Broadcast:</b>\n"
        "‣ /broadcast -user (Reply)\n"
        "‣ /broadcast -group (Reply)\n"
        "‣ <i>Flag:</i> -clean\n\n"
        "<b>👑 Owner Only:</b>\n"
        "‣ /update\n"
        "‣ /addsudo [user]\n"
        "‣ /rmsudo [user]\n"
        "‣ /cleandb\n"
        "‣ /sudolist"
    )

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ==============================
# 🔄 UPDATE BOT
# ==============================

async def update_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if not UPSTREAM_REPO:
        return await update.message.reply_text("❌ UPSTREAM_REPO missing!")

    msg = await update.message.reply_text("🔄 Checking updates...")

    try:
        import git

        try:
            repo = git.Repo()
        except:
            repo = git.Repo.init()
            origin = repo.create_remote('origin', UPSTREAM_REPO)
            origin.fetch()
            repo.create_head('main', origin.refs.main).set_tracking_branch(origin.refs.main).checkout()

        repo_url = UPSTREAM_REPO
        if GIT_TOKEN and "https://github.com" in repo_url:
            repo_url = repo_url.replace("https://", f"https://{GIT_TOKEN}@")

        repo.remotes.origin.set_url(repo_url)
        repo.remotes.origin.pull()

        await msg.edit_text("✅ Updated! Restarting...")

        os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as e:
        await msg.edit_text(f"❌ Update Failed: <code>{e}</code>", parse_mode=ParseMode.HTML)


# ==============================
# 👑 SUDO LIST
# ==============================

async def sudolist(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = "👑 <b>Owner & Sudo Users:</b>\n\n"

    owner_doc = users_collection.find_one({"user_id": OWNER_ID})

    if owner_doc:
        msg += f"👑 {get_mention(owner_doc)} (Owner)\n"
    else:
        msg += f"👑 <code>{OWNER_ID}</code>\n"

    for uid in SUDO_USERS:
        if uid == OWNER_ID:
            continue

        u_doc = users_collection.find_one({"user_id": uid})
        if u_doc:
            msg += f"👮 {get_mention(u_doc)}\n"
        else:
            msg += f"👮 <code>{uid}</code>\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ==============================
# ⚠️ CONFIRM SYSTEM
# ==============================

def get_kb(act, arg):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"cnf|{act}|{arg}"),
            InlineKeyboardButton("❌ No", callback_data="cnf|cancel|0")
        ]
    ])


async def ask(update, text, act, arg):
    await update.message.reply_text(
        f"⚠️ {text}\nAre you sure?",
        reply_markup=get_kb(act, arg),
        parse_mode=ParseMode.HTML
    )


def parse_amount_and_target(args):
    amount, target = None, None
    for arg in args:
        if arg.isdigit() and amount is None:
            amount = int(arg)
        else:
            target = arg
    return amount, target


# ==============================
# ⚡ COMMANDS
# ==============================

async def addsudo(update, context):
    if update.effective_user.id != OWNER_ID:
        return

    target, err = await resolve_target(update, context)
    if not target:
        return await update.message.reply_text(err or "Usage: /addsudo <user>")

    if target['user_id'] in SUDO_USERS:
        return await update.message.reply_text("Already Sudo")

    await ask(update, f"Promote {get_mention(target)}?", "addsudo", str(target['user_id']))


async def rmsudo(update, context):
    if update.effective_user.id != OWNER_ID:
        return

    target, err = await resolve_target(update, context)
    if not target:
        return await update.message.reply_text(err)

    await ask(update, f"Demote {get_mention(target)}?", "rmsudo", str(target['user_id']))


async def addcoins(update, context):
    if update.effective_user.id not in SUDO_USERS:
        return

    amount, target_str = parse_amount_and_target(context.args)
    target, err = await resolve_target(update, context, target_str)

    if not target:
        return await update.message.reply_text(err)

    await ask(update, f"Give {format_money(amount)} to {get_mention(target)}?", "addcoins", f"{target['user_id']}|{amount}")


async def rmcoins(update, context):
    if update.effective_user.id not in SUDO_USERS:
        return

    amount, target_str = parse_amount_and_target(context.args)
    target, err = await resolve_target(update, context, target_str)

    if not target:
        return await update.message.reply_text(err)

    await ask(update, f"Remove {format_money(amount)} from {get_mention(target)}?", "rmcoins", f"{target['user_id']}|{amount}")


async def freerevive(update, context):
    if update.effective_user.id not in SUDO_USERS:
        return

    target, err = await resolve_target(update, context)
    if not target:
        return await update.message.reply_text(err)

    await ask(update, f"Revive {get_mention(target)}?", "freerevive", str(target['user_id']))


async def unprotect(update, context):
    if update.effective_user.id not in SUDO_USERS:
        return

    target, err = await resolve_target(update, context)
    if not target:
        return await update.message.reply_text(err)

    await ask(update, f"Remove protection from {get_mention(target)}?", "unprotect", str(target['user_id']))


async def cleandb(update, context):
    if update.effective_user.id != OWNER_ID:
        return

    await ask(update, "WIPE DATABASE?", "cleandb", "0")


# ==============================
# 🔘 CONFIRM HANDLER
# ==============================

async def confirm_handler(update, context):
    q = update.callback_query
    await q.answer()

    data = q.data.split("|")
    act = data[1]

    if act == "cancel":
        return await q.message.edit_text("Cancelled")

    if act == "addsudo":
        uid = int(data[2])
        sudoers_collection.insert_one({"user_id": uid})
        reload_sudoers()
        await q.message.edit_text(f"Added sudo {uid}")

    elif act == "rmsudo":
        uid = int(data[2])
        sudoers_collection.delete_one({"user_id": uid})
        reload_sudoers()
        await q.message.edit_text(f"Removed sudo {uid}")

    elif act == "addcoins":
        uid, amt = map(int, data[2].split("|"))
        users_collection.update_one({"user_id": uid}, {"$inc": {"balance": amt}})
        await q.message.edit_text("Coins added")

    elif act == "rmcoins":
        uid, amt = map(int, data[2].split("|"))
        users_collection.update_one({"user_id": uid}, {"$inc": {"balance": -amt}})
        await q.message.edit_text("Coins removed")

    elif act == "freerevive":
        uid = int(data[2])
        users_collection.update_one({"user_id": uid}, {"$set": {"status": "alive"}})
        await q.message.edit_text("Revived")

    elif act == "unprotect":
        uid = int(data[2])
        users_collection.update_one({"user_id": uid}, {"$set": {"protection_expiry": datetime.utcnow()}})
        await q.message.edit_text("Protection removed")

    elif act == "cleandb":
        users_collection.delete_many({})
        groups_collection.delete_many({})
        await q.message.edit_text("Database cleared")
