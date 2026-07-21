import { json } from '@sveltejs/kit';

/** Keep the Concept Forge browser boundary JSON-only, including upstream failures. */
export async function conceptForgeJsonResponse(response: Response): Promise<Response> {
  try {
    return json(await response.json(), { status: response.status });
  } catch {
    return json(
      { error: 'Concept Forge could not read the server response. Please try again.' },
      { status: response.ok ? 502 : response.status },
    );
  }
}

export async function proxyConceptForge(
  fetchUpstream: () => Promise<Response>,
): Promise<Response> {
  try {
    return await conceptForgeJsonResponse(await fetchUpstream());
  } catch {
    return json(
      { error: 'Concept Forge is temporarily unavailable. Please try again.' },
      { status: 502 },
    );
  }
}
