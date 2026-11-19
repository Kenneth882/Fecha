/**
 * An unsigned JWT-shaped access token that expires `secondsLeft` from now. The web app
 * only reads `exp` to know when to refresh; FastAPI is what checks the signature.
 */
export function accessTokenExpiringIn(secondsLeft: number): string {
  const part = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const exp = Math.floor(Date.now() / 1000) + secondsLeft;
  return `${part({ alg: "HS256", typ: "JWT" })}.${part({ sub: "user-1", exp })}.signature`;
}
