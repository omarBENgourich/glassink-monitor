"use strict";

const assert = require("node:assert/strict");

const escapeTag = (value) => String(value)
    .replaceAll("\\", "\\\\")
    .replaceAll(" ", "\\ ")
    .replaceAll(",", "\\,")
    .replaceAll("=", "\\=");

const escapeKey = escapeTag;

function fieldValue(value) {
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "number") return Number.isFinite(value) ? String(value) : null;
    if (typeof value === "string") {
        return `"${value.replaceAll("\\", "\\\\").replaceAll('"', '\\"')}"`;
    }
    return null;
}

function point(measurement, tags, fields, timestampMs) {
    const tagSet = Object.entries(tags)
        .filter(([, value]) => value !== undefined && value !== null && value !== "")
        .map(([key, value]) => `${escapeKey(key)}=${escapeTag(value)}`)
        .join(",");
    const fieldSet = Object.entries(fields)
        .map(([key, value]) => [escapeKey(key), fieldValue(value)])
        .filter(([, value]) => value !== null)
        .map(([key, value]) => `${key}=${value}`)
        .join(",");

    if (!fieldSet) throw new Error("InfluxDB point has no supported fields");
    const timestamp = Number(timestampMs);
    if (!Number.isFinite(timestamp)) throw new Error("InfluxDB timestamp must be epoch milliseconds");
    return `${escapeKey(measurement)}${tagSet ? `,${tagSet}` : ""} ${fieldSet} ${Math.trunc(timestamp)}`;
}

function request(line) {
    const base = process.env.INFLUXDB_URL || "http://influxdb:8086";
    const org = encodeURIComponent(process.env.INFLUXDB_ORG || "saint-gobain");
    const bucket = encodeURIComponent(process.env.INFLUXDB_BUCKET || "printer_monitoring");
    const token = process.env.INFLUXDB_TOKEN;
    if (!token) throw new Error("INFLUXDB_TOKEN is required");
    return {
        method: "POST",
        url: `${base}/api/v2/write?org=${org}&bucket=${bucket}&precision=ms`,
        headers: {
            authorization: `Token ${token}`,
            "content-type": "text/plain; charset=utf-8",
            accept: "application/json",
        },
        payload: line,
    };
}

module.exports = { point, request };

if (require.main === module) {
    const line = point(
        "printer telemetry",
        { printer_id: "CIJ,01", state: "idle jet" },
        { level: 41.5, ok: true, note: 'a "test"' },
        1_750_000_000_000,
    );
    assert.equal(
        line,
        'printer\\ telemetry,printer_id=CIJ\\,01,state=idle\\ jet level=41.5,ok=true,note="a \\"test\\"" 1750000000000',
    );
    console.log("line protocol self-check OK");
}
