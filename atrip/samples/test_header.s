SDLSTL	= $0230 
CONSOL	= $D01F 
;
	*= $0600 
;
INIT
	LDA #<TITLEDL
	STA SDLSTL
	LDA #>TITLEDL
	STA SDLSTL+1 
	LDA #8 
	STA CONSOL
TTL0	LDA CONSOL
	CMP #6 
	BNE TTL0
	RTS 
;
TITLESC
	.SBYTE +$80 ,"   PRESS START TO   "
	.SBYTE +$C0 ,"  CONTINUE LOADING  "
;
TITLEDL	.BYTE $70 ,$70 ,$70
	.BYTE $70 ,$70 ,$70 ,$70 ,$70 ,$70 ,$70 ,$70 ,$70 ,$70 ,$47 
	.WORD TITLESC
	.BYTE 6 ,$41 
	.WORD TITLEDL

	*= $02E2 
	.WORD INIT
