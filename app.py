"""
app.py
------
Web layer (Flask). Ties the database + algorithms modules together and
exposes them as a browser-based system, per the brief's "running as a
web-based system" requirement.

Routes:
    GET  /                 -> dashboard: visual slot display + entry form
    POST /entry             -> Vehicle Entry module (park a car)
    GET  /checkout           -> preview fee for a plate before paying
    POST /checkout/confirm   -> Vehicle Exit + Payment + Barrier module
    GET  /history            -> log of completed sessions (from the DB)
"""

from flask import Flask, render_template, request, redirect, url_for, flash

from database import init_db, get_conn
from algorithms import SlotManager

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

# One SlotManager instance shared for the app's lifetime - it is the live
# in-memory brain of the car park, backed by SQLite (see algorithms.py).
init_db()
manager = SlotManager()


@app.route("/")
def dashboard():
    slots = manager.get_slot_display()
    return render_template(
        "index.html",
        slots=slots,
        available=manager.available_count(),
        total=len(slots),
    )


@app.route("/entry", methods=["POST"])
def entry():
    plate = request.form.get("plate_number", "")
    if not plate.strip():
        flash("Please enter a number plate.", "error")
        return redirect(url_for("dashboard"))

    ok, result = manager.park_vehicle(plate)
    if ok:
        flash(f"Vehicle {plate.strip().upper()} parked in slot {result}.", "success")
    else:
        flash(result, "error")
    return redirect(url_for("dashboard"))


@app.route("/checkout", methods=["GET"])
def checkout_preview():
    plate = request.args.get("plate_number", "")
    preview = manager.preview_fee(plate) if plate else None
    if plate and not preview:
        flash("No active session found for that plate.", "error")
    return render_template("checkout.html", preview=preview, plate=plate)


@app.route("/checkout/confirm", methods=["POST"])
def checkout_confirm():
    plate = request.form.get("plate_number", "")
    ok, result = manager.checkout_vehicle(plate)
    if not ok:
        flash(result, "error")
        return redirect(url_for("dashboard"))
    return render_template("receipt.html", receipt=result)


@app.route("/history")
def history():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.plate_number, sl.slot_number, s.entry_time, s.exit_time, s.fee, s.status
            FROM sessions s
            JOIN slots sl ON sl.id = s.slot_id
            ORDER BY s.id DESC
            LIMIT 100
            """
        ).fetchall()
    return render_template("history.html", rows=rows)


if __name__ == "__main__":
    # host=0.0.0.0 so it's reachable on a local network (e.g. a barrier
    # kiosk / display screen at the gate), debug=True for development only.
    app.run(host="0.0.0.0", port=5000, debug=True)
