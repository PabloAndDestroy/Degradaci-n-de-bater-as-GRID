export class ApiError extends Error {
  details: string[];

  constructor(message: string, details: string[] = []) {
    super(message);
    this.details = details;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json();
  if (!response.ok) {
    const details = Array.isArray(data.details)
      ? data.details.map(String)
      : Array.isArray(data.detail)
        ? data.detail.map((item: unknown) => {
            if (typeof item === "string") return item;
            if (!item || typeof item !== "object") return String(item);

            const validationError = item as { loc?: unknown[]; msg?: unknown };
            const location = Array.isArray(validationError.loc)
              ? validationError.loc.filter((part) => part !== "body").join(".")
              : "";
            const message = typeof validationError.msg === "string"
              ? validationError.msg
              : "Solicitud no válida.";
            return location ? `${location}: ${message}` : message;
          })
        : typeof data.detail === "string"
          ? [data.detail]
          : [];
    const message = data.error || (response.status === 422 ? "La solicitud no es válida." : response.statusText);
    throw new ApiError(message, details);
  }
  return data as T;
}

export function getJson<T>(url: string): Promise<T> {
  return request<T>(url);
}

export function postJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
