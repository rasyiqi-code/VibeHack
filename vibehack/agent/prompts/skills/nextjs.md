### Next.js & Vercel Tactical Intelligence
If you detect the target is a **Next.js** application:
1. **Source Discovery**: Search for `<script id="__NEXT_DATA__" type="application/json">`. This contains high-value metadata, including `buildId`, initial page props, and server-side state.
2. **Path Enumeration**: Don't rely on generic wordlists. Check `/_next/static/chunks/app-manifest.json` and `/_next/static/[buildId]/_buildManifest.js`.
3. **Chunk Analysis**: Look for specific route chunks in `/_next/static/chunks/pages/[route]-[hash].js`.
4. **Environment Leak**: If the app is misconfigured, sensitive keys might be exposed in the client-side hydration state (`props.pageProps`).
5. **Vercel Headers**: Check `x-vercel-id` and `x-matched-path` headers to identify the underlying routing logic.
