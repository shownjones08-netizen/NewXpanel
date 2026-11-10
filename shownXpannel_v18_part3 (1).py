#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHOWN X PANEL BOT — v18.0-U1
PART 3 — Callback Handler · Error Handler · main()
"""

# ══════════════════════════════════════════════════════════════════
#  MASTER CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q    = update.callback_query
    data = q.data or ""
    user = q.from_user
    await q.answer()

    # ── noop ───────────────────────────────────────────────────
    if data == "noop":
        return

    # ── home ───────────────────────────────────────────────────
    if data == "home":
        admin = is_admin(user.id)
        try: await q.message.delete()
        except Exception: pass
        await context.bot.send_message(user.id, "🏠 Main Menu",
            reply_markup=main_menu_kb(admin))
        return

    # ── admin:home ─────────────────────────────────────────────
    if data == "admin:home":
        try: await q.message.delete()
        except Exception: pass
        brand = await get_setting("bot_brand_name", BOT_BRAND_NAME)
        await context.bot.send_message(user.id,
            ui_screen("👑", f"{brand} — Admin Panel", ui_box("Select a section below")),
            parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())
        return

    # ══ STATUS REFRESH ════════════════════════════════════════
    if data == "status:refresh":
        alive = sum(1 for h in _fb_health.values() if h.get("status")=="alive")
        dead  = sum(1 for h in _fb_health.values() if h.get("status")=="dead")
        poll_int = await gsint("poll_interval", POLL_INTERVAL)
        maint    = await gsbool("maintenance_mode", False)
        mon_on   = user.id in _monitor_subs
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
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except BadRequest: pass
        return

    # ══ DB MANAGER ════════════════════════════════════════════
    if data.startswith("db:page:"):
        if not is_admin(user.id): return
        page = int(data.split(":")[-1])
        try: await q.edit_message_reply_markup(reply_markup=db_panel_kb(page))
        except BadRequest: pass
        return

    if data.startswith("db:view:"):
        safe_name = data[8:]
        # Reverse safe_cb to find original name
        name = next((n for n in DATABASES if safe_cb(n)==safe_name), safe_name)
        url  = DATABASES.get(name, "")
        h    = _fb_health.get(name, {})
        icon = db_status_icon(name)
        async with db() as c:
            meta = c.execute("SELECT notes,tag,priority FROM db_meta WHERE db_name=?", (name,)).fetchone()
        notes    = meta["notes"]    if meta else ""
        tag      = meta["tag"]      if meta else ""
        priority = meta["priority"] if meta else 0
        last_check = "—"
        if h.get("last_check"):
            last_check = datetime.fromtimestamp(h["last_check"]).strftime("%H:%M:%S")
        text = ui_screen(icon, f"DB: {name}",
            ui_box(
                ui_kv("🔗","URL",    f"<code>{he(url[:60])}</code>"),
                ui_kv("📊","Status", (h.get("status","unknown")).upper()),
                ui_kv("🕐","Checked",last_check),
                ui_kv("🏷","Tag",    he(tag) if tag else "—"),
                ui_kv("⭐","Priority",str(priority)),
            ),
            ui_box(f"📝 {he(notes)}") if notes else "",
        )
        kb = InlineKeyboardMarkup([
            [_ikb("🔥 Ping",        callback_data=f"db:ping:{safe_name}",       style="success"),
             _ikb("🧬 Clone",       callback_data=f"db:clone_this:{safe_name}", style="primary")],
            [_ikb("📝 Add Notes",   callback_data=f"db:notes:{safe_name}",      style="primary"),
             _ikb("🗑 Remove",      callback_data=f"db:remove:{safe_name}",     style="danger")],
            back_row("admin:home"),
        ])
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except BadRequest: pass
        return

    if data.startswith("db:ping:"):
        safe_name = data[8:]
        name = next((n for n in DATABASES if safe_cb(n)==safe_name), safe_name)
        url  = DATABASES.get(name, "")
        if not url: await q.answer("DB not found", show_alert=True); return
        session = await get_session()
        alive = await _ping_fb(url, session)
        status = "🟢 ALIVE" if alive else "🔴 DEAD"
        _fb_health[name] = {"status":"alive" if alive else "dead", "last_check":time.time(), "url":url}
        await q.answer(f"{name}: {status}", show_alert=True)
        return

    if data.startswith("db:remove:"):
        if not is_admin(user.id): return
        safe_name = data[10:]
        name = next((n for n in DATABASES if safe_cb(n)==safe_name), safe_name)
        DATABASES.pop(name, None)
        _fb_health.pop(name, None)
        await q.answer(f"✅ Removed {name}")
        try: await q.edit_message_reply_markup(reply_markup=db_panel_kb(0))
        except BadRequest: pass
        return

    if data == "db:health":
        if not is_admin(user.id): return
        await q.answer("⏳ Checking...")
        session = await get_session()
        results = await run_health_check(session)
        alive = sum(1 for s in results.values() if s=="alive")
        dead  = sum(1 for s in results.values() if s=="dead")
        await q.answer(f"✅ {alive} alive, {dead} dead", show_alert=True)
        try: await q.edit_message_reply_markup(reply_markup=db_panel_kb(0))
        except BadRequest: pass
        return

    if data == "db:remove_dead":
        if not is_admin(user.id): return
        count = await remove_dead_dbs()
        await q.answer(f"🗑 Removed {count} dead DBs", show_alert=True)
        try: await q.edit_message_reply_markup(reply_markup=db_panel_kb(0))
        except BadRequest: pass
        return

    if data == "db:add":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"add_db"}
        await context.bot.send_message(user.id,
            "📥 <b>Send DB info:</b>\n\n<code>DB_NAME https://your-firebase-url</code>",
            parse_mode=ParseMode.HTML)
        return

    if data == "db:import":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"import_dbs"}
        await context.bot.send_message(user.id,
            "📥 <b>Send JSON to import databases:</b>\n\n"
            "<code>{\"DB_NAME\": \"https://url\", ...}</code>",
            parse_mode=ParseMode.HTML)
        return

    if data.startswith("db:clone_this:"):
        if not is_admin(user.id): return
        safe_name = data[14:]
        name = next((n for n in DATABASES if safe_cb(n)==safe_name), safe_name)
        pending_action[user.id] = {"action":"clone_db"}
        await context.bot.send_message(user.id,
            f"🧬 <b>Clone:</b> <code>{he(name)}</code>\n\n"
            f"Send: <code>{he(name)} NEW_NAME</code>",
            parse_mode=ParseMode.HTML)
        return

    if data.startswith("db:notes:"):
        if not is_admin(user.id): return
        safe_name = data[9:]
        name = next((n for n in DATABASES if safe_cb(n)==safe_name), safe_name)
        pending_action[user.id] = {"action":"set_db_notes", "db_name":name}
        await context.bot.send_message(user.id,
            f"📝 <b>Add notes for:</b> <code>{he(name)}</code>\n\nSend your notes:",
            parse_mode=ParseMode.HTML)
        return

    # ══ MONITOR ═══════════════════════════════════════════════
    if data == "monitor:toggle":
        new_state = await toggle_monitor(user.id)
        await q.answer(f"📡 Monitor: {'🟢 ON' if new_state else '🔴 OFF'}", show_alert=True)
        return

    if data == "monitor:edit_fmt":
        if not is_admin(user.id): return
        async with db() as c:
            fmt_row = c.execute("SELECT template FROM otp_format WHERE id=1").fetchone()
        current = fmt_row["template"] if fmt_row else ""
        pending_action[user.id] = {"action":"set_otp_format"}
        await context.bot.send_message(user.id,
            f"✏️ <b>Current OTP format:</b>\n<code>{he(current)}</code>\n\n"
            f"<b>Variables:</b> <code>{{phone}}</code> <code>{{otp}}</code> "
            f"<code>{{db}}</code> <code>{{time}}</code>\n\nSend new format:",
            parse_mode=ParseMode.HTML)
        return

    if data == "monitor:set_fwd":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_forward_channel"}
        await context.bot.send_message(user.id,
            "📡 <b>Send channel ID to forward OTPs:</b>\n<i>(e.g. -100xxxxxxxxx)</i>",
            parse_mode=ParseMode.HTML)
        return

    # ══ HUB ═══════════════════════════════════════════════════
    if data.startswith("hub:page:"):
        page = int(data.split(":")[-1])
        await _show_hub(update, context, user.id, page, edit=True)
        return

    if data == "hub:clear":
        async with db() as c:
            c.execute("DELETE FROM user_hub WHERE user_id=?", (user.id,))
        await q.answer("🗑 History cleared", show_alert=True)
        await _show_hub(update, context, user.id, 0, edit=True)
        return

    if data == "hub:search":
        pending_action[user.id] = {"action":"search_hub"}
        await context.bot.send_message(user.id, "🔍 <b>Send phone number to search:</b>",
            parse_mode=ParseMode.HTML)
        return

    if data == "hub:export":
        async with db() as c:
            rows = c.execute("SELECT phone,otp,db_name,timestamp FROM user_hub "
                             "WHERE user_id=? ORDER BY timestamp DESC", (user.id,)).fetchall()
        if not rows:
            await q.answer("📭 No data to export", show_alert=True); return
        lines = ["phone,otp,db_name,timestamp"]
        for r in rows:
            lines.append(f"{r['phone']},{r['otp'] or ''},{r['db_name'] or ''},{ r['timestamp']}")
        csv_data = "\n".join(lines).encode()
        fname = f"hub_export_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        await context.bot.send_document(user.id, io.BytesIO(csv_data), filename=fname,
            caption=f"📤 <b>Hub Export</b> · {len(rows)} records",
            parse_mode=ParseMode.HTML)
        await q.answer("✅ Exported!")
        return

    # ══ BACKUP ════════════════════════════════════════════════
    if data == "backup:now":
        if not is_admin(user.id): return
        await q.answer("⏳ Sending...")
        ok = await send_backup(context.bot, user.id)
        await q.answer("✅ Backup sent!" if ok else "❌ Failed", show_alert=True)
        return

    if data == "backup:toggle_auto":
        if not is_admin(user.id): return
        cur = await gsbool("auto_db_enabled", False)
        await set_setting("auto_db_enabled", "0" if cur else "1")
        await q.answer(f"Auto backup: {'OFF' if cur else 'ON'}", show_alert=True)
        return

    if data == "backup:set_target":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_backup_target"}
        await context.bot.send_message(user.id,
            "📤 <b>Send primary backup target chat ID:</b>", parse_mode=ParseMode.HTML)
        return

    if data == "backup:add_target":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"add_backup_target"}
        await context.bot.send_message(user.id,
            "➕ <b>Send additional backup target chat ID:</b>", parse_mode=ParseMode.HTML)
        return

    if data == "backup:extra_list":
        if not is_admin(user.id): return
        targets = await gsjson("multi_backup_targets", [])
        lines   = [f"📤 <code>{t}</code>" for t in targets]
        text    = ui_screen("📋","Extra Backup Targets",
            ui_box("\n".join(lines) if lines else "📭 None added."))
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([back_row("admin:home")]))
        except BadRequest: pass
        return

    if data == "backup:history":
        if not is_admin(user.id): return
        history = await get_backup_history(10)
        lines   = [f"📦 {fmt_dt(h['timestamp'])} · {fmt_size(h.get('size_bytes') or 0)}\n"
                   f"   {he(h.get('filename','—'))}" for h in history]
        text    = ui_screen("💾","Backup History",
            ui_box("\n\n".join(lines) if lines else "📭 No backups yet."))
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([back_row("admin:home")]))
        except BadRequest: pass
        return

    # ══ CLONE ═════════════════════════════════════════════════
    if data == "clone:start":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"clone_db"}
        await context.bot.send_message(user.id,
            "🧬 <b>Clone a DB</b>\n\nSend: <code>SOURCE_NAME NEW_NAME</code>",
            parse_mode=ParseMode.HTML)
        return

    if data.startswith("clone:list:"):
        if not is_admin(user.id): return
        page  = int(data.split(":")[-1])
        per   = 5
        clones = await get_clones()
        items  = clones[page*per:(page+1)*per]
        total_pages = max(1,(len(clones)+per-1)//per)
        lines  = [f"🧬 <b>{he(c['name'])}</b> ← {he(c.get('source_name') or '?')}\n"
                  f"   📅 {fmt_dt(c.get('created_at'))}" for c in items]
        text   = ui_screen("🧬","Clone List",
            ui_box("\n\n".join(lines) if lines else "📭 None."),
            subtitle=f"Page {page+1}/{total_pages}")
        nav = []
        if page > 0: nav.append(_ikb("⬅️", callback_data=f"clone:list:{page-1}", style="primary"))
        if page < total_pages-1: nav.append(_ikb("➡️", callback_data=f"clone:list:{page+1}", style="primary"))
        rows_kb = [nav] if nav else []
        rows_kb.append(back_row("admin:home"))
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows_kb))
        except BadRequest: pass
        return

    # ══ CUSTOMIZE ═════════════════════════════════════════════
    if data == "cust:text_a":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_welcome_text"}
        await context.bot.send_message(user.id,
            "✏️ <b>Send Welcome Text (A):</b>", parse_mode=ParseMode.HTML)
        return

    if data == "cust:text_b":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_welcome_text_b"}
        await context.bot.send_message(user.id,
            "✏️ <b>Send Welcome Text (B):</b>", parse_mode=ParseMode.HTML)
        return

    if data == "cust:media_a":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_welcome_media"}
        await context.bot.send_message(user.id,
            "🖼 <b>Send photo/video/GIF for Welcome (A):</b>", parse_mode=ParseMode.HTML)
        return

    if data == "cust:media_b":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_welcome_media_b"}
        await context.bot.send_message(user.id,
            "🖼 <b>Send photo/video/GIF for Welcome (B):</b>", parse_mode=ParseMode.HTML)
        return

    if data == "cust:clr_a":
        if not is_admin(user.id): return
        await clear_welcome_media("a")
        await q.answer("🗑 Media A cleared", show_alert=True)
        return

    if data == "cust:clr_b":
        if not is_admin(user.id): return
        await clear_welcome_media("b")
        await q.answer("🗑 Media B cleared", show_alert=True)
        return

    if data == "cust:preview":
        text, mid, mt = await build_welcome(user)
        await send_rich_or_fallback(context.bot, user.id, text, mid, mt)
        await q.answer("👁 Preview sent")
        return

    if data == "cust:brand":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_brand"}
        await context.bot.send_message(user.id,
            "🏷 <b>Send new brand name:</b>", parse_mode=ParseMode.HTML)
        return

    # ══ USERS ═════════════════════════════════════════════════
    if data == "user:grant":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"grant_user"}
        await context.bot.send_message(user.id, "📨 Send User ID to grant access:")
        return

    if data == "user:revoke":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"revoke_user"}
        await context.bot.send_message(user.id, "🚫 Send User ID to revoke access:")
        return

    if data == "user:add_admin":
        if user.id != OWNER_ID: return
        pending_action[user.id] = {"action":"add_admin"}
        await context.bot.send_message(user.id, "👑 Send User ID to make admin:")
        return

    if data.startswith("user:list:"):
        if not is_admin(user.id): return
        page = int(data.split(":")[-1])
        per  = 10
        items = list(allowed_users)
        chunk = items[page*per:(page+1)*per]
        total_pages = max(1,(len(items)+per-1)//per)
        lines = [f"🔑 <code>{uid}</code>" for uid in chunk]
        text  = ui_screen("👥","Allowed Users",
            ui_box("\n".join(lines) if lines else "📭 None."),
            subtitle=f"Page {page+1}/{total_pages}")
        nav = []
        if page > 0: nav.append(_ikb("⬅️", callback_data=f"user:list:{page-1}", style="primary"))
        if page < total_pages-1: nav.append(_ikb("➡️", callback_data=f"user:list:{page+1}", style="primary"))
        rows_kb = [nav] if nav else []
        rows_kb.append(back_row("admin:home"))
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows_kb))
        except BadRequest: pass
        return

    if data == "user:broadcast":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"broadcast"}
        await context.bot.send_message(user.id,
            "📡 <b>Send broadcast message:</b>\n<i>HTML formatting supported.</i>",
            parse_mode=ParseMode.HTML)
        return

    if data == "user:search":
        if not is_admin(user.id): return
        await q.answer("🔍 Use /id or search by username — coming in next update", show_alert=True)
        return

    # ══ BAN MANAGER ═══════════════════════════════════════════
    if data == "ban:add":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"ban_user"}
        await context.bot.send_message(user.id,
            "🚫 <b>Send ban info:</b>\n<code>USER_ID [hours] [reason]</code>\n\n"
            "<i>hours=0 means permanent</i>", parse_mode=ParseMode.HTML)
        return

    if data == "ban:remove":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"unban_user"}
        await context.bot.send_message(user.id, "✅ Send User ID to unban:")
        return

    if data.startswith("ban:list:"):
        if not is_admin(user.id): return
        page = int(data.split(":")[-1])
        per  = 8
        items = list(banned_users.items())
        chunk = items[page*per:(page+1)*per]
        total_pages = max(1,(len(items)+per-1)//per)
        lines = []
        for uid_b, info in chunk:
            reason = info.get("reason","—")
            until  = fmt_dt(info.get("until")) if info.get("until") else "Permanent"
            lines.append(f"🚫 <code>{uid_b}</code> · {he(reason[:30])}\n   ⏱ {until}")
        text = ui_screen("🚫","Banned Users",
            ui_box("\n\n".join(lines) if lines else "✅ No banned users."),
            subtitle=f"Page {page+1}/{total_pages}")
        nav = []
        if page > 0: nav.append(_ikb("⬅️", callback_data=f"ban:list:{page-1}", style="primary"))
        if page < total_pages-1: nav.append(_ikb("➡️", callback_data=f"ban:list:{page+1}", style="primary"))
        rows_kb = [nav] if nav else []
        rows_kb.append(back_row("admin:home"))
        try: await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows_kb))
        except BadRequest: pass
        return

    # ══ SETTINGS ══════════════════════════════════════════════
    if data == "settings:toggle_grant":
        if not is_admin(user.id): return
        cur = await gsbool("grant_access_required", True)
        await set_setting("grant_access_required", "0" if cur else "1")
        await q.answer(f"Access control: {'OFF' if cur else 'ON'}", show_alert=True)
        return

    if data == "settings:toggle_referral":
        if not is_admin(user.id): return
        cur = await gsbool("referral_enabled", True)
        await set_setting("referral_enabled", "0" if cur else "1")
        await q.answer(f"Referral: {'OFF' if cur else 'ON'}", show_alert=True)
        return

    if data == "settings:toggle_maint":
        if not is_admin(user.id): return
        cur = await gsbool("maintenance_mode", False)
        await set_setting("maintenance_mode", "0" if cur else "1")
        await q.answer(f"Maintenance: {'OFF' if cur else 'ON'}", show_alert=True)
        return

    if data == "settings:toggle_wl":
        if not is_admin(user.id): return
        cur = await gsbool("whitelist_mode", False)
        await set_setting("whitelist_mode", "0" if cur else "1")
        await q.answer(f"Whitelist mode: {'OFF' if cur else 'ON'}", show_alert=True)
        return

    if data == "settings:poll":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_poll_interval"}
        await context.bot.send_message(user.id,
            "⏱ <b>Send poll interval (seconds, min 5):</b>", parse_mode=ParseMode.HTML)
        return

    if data == "settings:refs":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_refs_required"}
        await context.bot.send_message(user.id,
            "🔢 <b>Send referrals required (e.g. 2):</b>", parse_mode=ParseMode.HTML)
        return

    if data == "settings:rate":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_rate_limit"}
        await context.bot.send_message(user.id,
            "🚦 <b>Send max OTPs per minute per DB:</b>", parse_mode=ParseMode.HTML)
        return

    if data == "settings:stale":
        if not is_admin(user.id): return
        pending_action[user.id] = {"action":"set_stale_mins"}
        await context.bot.send_message(user.id,
            "⏰ <b>Send stale OTP threshold (minutes):</b>", parse_mode=ParseMode.HTML)
        return

    # ══ ANALYTICS ═════════════════════════════════════════════
    if data == "ana:export":
        if not is_admin(user.id): return
        async with db() as c:
            rows = c.execute(
                "SELECT db_name,phone,otp,timestamp FROM otp_analytics ORDER BY timestamp DESC"
            ).fetchall()
        if not rows:
            await q.answer("📭 No analytics data yet", show_alert=True); return
        lines = ["db_name,phone,otp,timestamp"]
        for r in rows:
            lines.append(f"{r['db_name']},{r['phone']},{r['otp'] or ''},{r['timestamp']}")
        csv_data = "\n".join(lines).encode()
        fname = f"otp_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        await context.bot.send_document(user.id, io.BytesIO(csv_data), filename=fname,
            caption=f"📊 <b>OTP Analytics Export</b> · {len(rows)} records",
            parse_mode=ParseMode.HTML)
        await q.answer("✅ Exported!")
        return


# ══════════════════════════════════════════════════════════════════
#  ERROR HANDLER
# ══════════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, (Conflict, asyncio.CancelledError)): return
    if isinstance(err, RetryAfter):
        await asyncio.sleep(err.retry_after); return
    if isinstance(err, (Forbidden, ChatMigrated, BadRequest)): return
    log.error("Update error: %s", traceback.format_exc())


# ══════════════════════════════════════════════════════════════════
#  POST INIT
# ══════════════════════════════════════════════════════════════════

async def post_init(app: Application) -> None:
    await init_db()
    await _init_defaults()
    await migrate_from_json()
    await load_access_data()
    await load_monitor_subs()

    app.create_task(poll_loop(app.bot),         name="poll_loop")
    app.create_task(auto_backup_loop(app.bot),  name="backup_loop")
    app.create_task(health_loop(app.bot),       name="health_loop")
    app.create_task(ban_expiry_loop(),          name="ban_expiry_loop")

    try:
        app.create_task(health_server(), name="health_server")
    except Exception as e:
        log.warning("Health server not started: %s", e)

    log.info("SHOWN X PANEL v18.0-U1 STARTED | DBs: %d | Allowed: %d | Admins: %d",
             len(DATABASES), len(allowed_users), len(ADMIN_IDS))


# ══════════════════════════════════════════════════════════════════
#  main()
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    global _main_app
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )
    _main_app = app

    # Commands
    for cmd, fn in [
        ("start",    cmd_start),
        ("panel",    cmd_panel),
        ("status",   cmd_status),
        ("hub",      cmd_hub),
        ("admin",    cmd_admin),
        ("help",     cmd_help),
        ("grant",    cmd_grant),
        ("revoke",   cmd_revoke),
        ("ban",      cmd_ban),
        ("unban",    cmd_unban),
        ("adddb",    cmd_adddb),
        ("removedb", cmd_removedb),
        ("backup",   cmd_backup),
        ("monitor",  cmd_monitor),
        ("health",   cmd_health),
        ("stats",    cmd_stats),
        ("addadmin", cmd_addadmin),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Media
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.ANIMATION,
        handle_media))

    # Text
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text))

    # Errors
    app.add_error_handler(error_handler)

    log.info("Starting polling...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()

# ═══ PART 3 ENDS HERE ═══
#
# ── MERGE INSTRUCTIONS ──────────────────────────────────────────
# Linux/Mac (one command):
#   cat <(head -n -3 part1.py) <(tail -n +6 part2.py | head -n -3) <(tail -n +6 part3.py) > final.py
#
# Manual:
#   1. Remove last 3 lines of Part 1 (# ═══ PART 1 ENDS HERE ═══ block)
#   2. Remove first 5 lines of Part 2 (shebang + docstring) AND last 3 lines
#   3. Remove first 5 lines of Part 3 (shebang + docstring)
#   4. Concatenate: Part1 + Part2 + Part3 → shownXpannel_v18_final.py
#   5. pip install -r requirements.txt
#   6. python shownXpannel_v18_final.py
