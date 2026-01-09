# How to Add Videos to README

## Option 1: YouTube/Vimeo Video (Recommended)

If your video is on YouTube or Vimeo, you can embed it using an image thumbnail that links to the video:

```markdown
[![Video Title](https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg)](https://www.youtube.com/watch?v=VIDEO_ID)
```

Or just a simple link:

```markdown
[Watch Demo Video](https://www.youtube.com/watch?v=VIDEO_ID)
```

## Option 2: HTML Video Tag (GitHub supports this)

For videos stored in your repository, you can use HTML:

```markdown
<video width="800" controls>
  <source src="docs/videos/demo.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>
```

**Note:** GitHub will display the video player, but the video file needs to be in your repository.

## Option 3: Animated GIF (Best for short clips)

Convert your video to a GIF and use it like an image:

```markdown
![Demo Animation](docs/images/demo.gif)
```

## Option 4: Direct Link

Just link to the video:

```markdown
📹 [Watch the demo video](https://your-video-url.com)
```

## Recommended Approach

1. **Upload to YouTube** (unlisted or public)
2. **Use thumbnail + link** in README:

```markdown
[![Clinical Anesthesia QA System Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
```

This gives you:
- ✅ Automatic thumbnail
- ✅ Clickable video
- ✅ No large files in your repo
- ✅ Works on all devices

