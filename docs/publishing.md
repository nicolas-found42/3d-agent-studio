# Maintain the docs site

Edit the same Markdown used on GitHub. The Pages overview lives in `index.md`. The repository README introduces the project on GitHub. `zensical.toml` defines the navigation. The build stages the public guides and media under their repository-relative paths. It also groups the bundled skill and references into topics for Pages. Edit those topics in their original Markdown files under `skills/3d-agent-studio/`.

## Preview a change

From the repository root, run a strict build. It checks local file destinations and heading anchors and writes the site to `build/docs-site`.

```sh
uv run --python 3.12 tools/docs_site.py build
```

For a live preview, use the same project URL prefix as GitHub Pages.

```sh
uv run --python 3.12 tools/docs_site.py serve
```

Open [the local preview](http://127.0.0.1:8000/3d-agent-studio/). Restart the preview after editing source files so it picks up a fresh copy. On desktop and mobile, check the pages you changed, including code blocks, image captions, and clip links. Link to Markdown files or assets explicitly so the same link works from GitHub and the generated site.

## Publish to GitHub Pages

The documentation workflow publishes the [Studio site](https://nicolas-found42.github.io/3d-agent-studio/) from `main`. To set up Pages for a new repository or fork, follow these steps.

1. In the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.
2. Once the workflow is on `main`, open **Actions → Documentation → Run workflow** and select `main`.
3. After the deployment job succeeds, open the `github-pages` URL and check that the overview, a deep docs link, and a gallery clip load.

Pull requests run the strict build. Pushes to `main` publish the built artifact through the `github-pages` environment. For a fork or custom domain, set `site_url`, `repo_url`, and `repo_name` in `zensical.toml` to match the new repository and Pages URL.

[GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) · [GitHub Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
