for (const poster of document.querySelectorAll(".studio-case__media a > img")) {
  const link = poster.parentElement;
  const button = document.createElement("button");
  const label = document.createElement("span");

  button.type = "button";
  button.className = "studio-play";
  button.setAttribute("aria-label", `Play draft: ${poster.alt}`);
  label.className = "studio-play__label";
  label.textContent = "Play draft";
  button.append(poster, label);
  link.replaceWith(button);

  button.addEventListener("click", () => {
    const video = document.createElement("video");
    video.controls = true;
    video.playsInline = true;
    video.poster = poster.src;
    video.src = link.href;
    video.setAttribute("aria-label", poster.alt);
    button.replaceWith(video);
    video.focus();
    video.play().catch(() => {
      video.focus();
    });
  });
}
