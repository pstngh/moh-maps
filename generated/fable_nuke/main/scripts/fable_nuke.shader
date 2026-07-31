textures/fable_nuke/chainlink
{
	qer_editorimage textures/fable_nuke/chainlink.tga
	surfaceparm trans
	surfaceparm nonsolid
	surfaceparm alphashadow
	surfaceparm nomarks
	cull none
	{
		map textures/fable_nuke/chainlink.tga
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

textures/fable_nuke/glass
{
	qer_editorimage textures/fable_nuke/glass.tga
	surfaceparm trans
	surfaceparm nonsolid
	surfaceparm nomarks
	cull none
	{
		map textures/fable_nuke/glass.tga
		blendFunc GL_SRC_ALPHA GL_ONE_MINUS_SRC_ALPHA
		rgbGen identity
	}
}
