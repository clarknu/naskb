window.ARCH_DATA = window.ARCH_DATA || {};
window.ARCH_DATA["security-policy"] = {
  auth: { webAdmin: { scheme: "JWT", tokenLifetime: "2h" }, device: { scheme: "MQTT 证书+JWT" } },
  authorization: { model: "RBAC + 资源域隔离" },
  sensitiveData: { encryption: { algorithm: "AES-256-GCM" } },
  deviceSecurity: { mqtt: { tls: "TLS1.2 双向" } }
};