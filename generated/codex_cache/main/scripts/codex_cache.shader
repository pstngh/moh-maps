textures/codex_cache/chainlink
{
	qer_editorimage textures/codex_cache/chainlink.tga
	surfaceparm trans
	surfaceparm nonsolid
	surfaceparm alphashadow
	surfaceparm nomarks
	cull none
	{
		map textures/codex_cache/chainlink.tga
		alphaFunc GE128
		depthWrite
		rgbGen identity
	}
	{
		map $lightmap
		blendFunc GL_DST_COLOR GL_ZERO
		depthFunc equal
	}
}

textures/codex_cache/window_backing
{
	qer_editorimage textures/codex_cache/window_backing.tga
	surfaceparm nolightmap
	surfaceparm nonsolid
	surfaceparm nomarks
	{
		map textures/codex_cache/window_backing.tga
		rgbGen identity
	}
}

textures/codex_cache/glass
{
	qer_editorimage textures/codex_cache/glass.tga
	surfaceparm trans
	surfaceparm nonsolid
	surfaceparm nomarks
	cull none
	{
		map textures/codex_cache/glass.tga
		blendFunc GL_SRC_ALPHA GL_ONE_MINUS_SRC_ALPHA
		rgbGen identity
	}
}
