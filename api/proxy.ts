export default async function handler(request, response) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return response.status(500).json({ error: "BACKEND_URL not configured" });
  }

  const target = `${backendUrl.replace(/\/$/, "")}${request.url}`;

  try {
    const fetchOptions = {
      method: request.method,
      headers: { ...request.headers },
    };

    if (request.body) {
      const body = await request.text();
      fetchOptions.body = body;
    }

    const res = await fetch(target, fetchOptions);
    const resHeaders = new Headers();
    res.headers.forEach((value, key) => resHeaders.set(key, value));
    resHeaders.delete("content-encoding");
    resHeaders.delete("content-length");
    resHeaders.set("access-control-allow-origin", "*");

    const contentType = resHeaders.get("content-type") || "";
    let body;
    if (contentType.includes("json")) {
      body = await res.json();
    } else {
      body = await res.text();
    }

    return new Response(JSON.stringify(body), {
      status: res.status,
      headers: resHeaders,
    });
  } catch (err) {
    return response.status(502).json({ error: "Backend unreachable", details: err.message });
  }
}
