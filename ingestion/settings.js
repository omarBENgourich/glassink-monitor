"use strict";

const bcrypt = require("bcryptjs");

const adminUser = process.env.NODE_RED_ADMIN_USER || "admin";
const adminPassword = process.env.NODE_RED_ADMIN_PASSWORD;
const credentialSecret = process.env.NODE_RED_CREDENTIAL_SECRET;

if (!adminPassword) {
    throw new Error("NODE_RED_ADMIN_PASSWORD is required");
}
if (!credentialSecret) {
    throw new Error("NODE_RED_CREDENTIAL_SECRET is required");
}

module.exports = {
    // Listen on the container interface. Docker still exposes the editor only
    // on host loopback via 127.0.0.1:1880.
    uiHost: "0.0.0.0",
    uiPort: Number(process.env.PORT || 1880),
    flowFile: "flows.json",
    credentialSecret,
    functionGlobalContext: {
        lineProtocol: require("./line_protocol"),
    },

    adminAuth: {
        type: "credentials",
        users: [{
            username: adminUser,
            password: bcrypt.hashSync(adminPassword, 10),
            permissions: "*",
        }],
    },

    diagnostics: {
        enabled: false,
        ui: false,
    },
    runtimeState: {
        enabled: false,
        ui: false,
    },
    editorTheme: {
        projects: { enabled: false },
    },
    externalModules: {
        autoInstall: false,
        palette: {
            allowInstall: false,
            allowUpload: false,
        },
        modules: {
            allowInstall: false,
        },
    },
    functionExternalModules: false,
    logging: {
        console: {
            level: process.env.NODE_RED_LOG_LEVEL || "info",
            metrics: false,
            audit: false,
        },
    },
};
