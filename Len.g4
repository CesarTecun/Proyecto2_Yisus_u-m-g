grammar Len;

// ===== Palabras clave =====
MOSTRAR: [Mm][Ss][Tt];
RET: [Rr][Ee][Tt];
PARA: [Ff][Oo][Rr];
SINO: [Nn][Oo];
HACER: [Dd][Oo];
SI: [Ss][Ii];
LOP: [Ll][Oo][Oo][Pp];
START: [Ii][Nn][Ii];
PROGRAM: [Pp][Rr][Oo][Gg];
END: [Ff][Ii][Nn];

// ===== Tipos de datos =====
CADENA: [Ss][Tt][Rr];
VAR: [Aa][Uu][Tt]; // Para declaraciones inferidas
BOOL: [Bb][Oo][Ll];
DECIMAL: [Ff][Ll][Tt];
VOID: [Vv][Dd];
ENTERO: [Ii][Nn][Tt];

// ===== Literales =====
TEXTO: '"' ( ~["\\\r\n] | '\\' . )* '"';
NUMERO: [0-9]+ ('.' [0-9]+)?;
BOOL_LIT: 'true' | 'false';

// ===== Identificadores =====
ID: [a-zA-Z][a-zA-Z0-9_]*;

// ===== Operadores y símbolos =====
O: '||';
MULT: '*';
ASIGN: '=';
PAR_IZQ: '(';
MAYOR: '>';
PUNTOCOMA: ';';
RESTA: '-';
DIF: '!=';
LLAVE_IZQ: '{';
MENOR: '<';
POTENCIA: '^';
PAR_DER: ')';
DIV: '/';
MAY_IGUAL: '>=';
COMA: ',';
Y: '&&';
LLAVE_DER: '}';
NOT: '!';
SUMA: '+';
IGUAL: '==';
MEN_IGUAL: '<=';
RESIDUO: '%';


// ===== Espacios y comentarios =====
WS: [ \t\r\n]+ -> skip;
COMENTARIO: '#' ~[\r\n]* -> skip;


prog
    : PROGRAM ID LLAVE_IZQ 
        ( 
            declaracion_global* funciones? bloque_PROGRAM 
            | declaracion_global* bloque_PROGRAM funciones? 
        ) 
      LLAVE_DER EOF
    ;

declaracion
    : tipo ID (ASIGN expr)? PUNTOCOMA       #declaracionSimple
    | VAR ID (ASIGN expr)? PUNTOCOMA        #declaracionInferida
    ;

declaracion_global
    : tipo ID (ASIGN expr)? PUNTOCOMA       #declaracionGlobalSimple
    ;

funciones
    : 'funs' LLAVE_IZQ funcion* LLAVE_DER
    ;

bloque_PROGRAM
    : START bloque END
    ;

bloque
    : LLAVE_IZQ sentencia* LLAVE_DER
    ;

funcion
    : (tipo | VOID) ID PAR_IZQ params PAR_DER bloque  #funcionDef
    ;

params
    : param (COMA param)*     #parametros
    | /* vacío */             #sinParametros
    ;

param
    : tipo ID                 #paramSimple
    ;

sentencia
    : declaracion                                                          #declaracionSentencia
     | asignacion PUNTOCOMA                                             #asignacionSentencia
    | expr PUNTOCOMA                                                       #exprSentencia
    | bloque                                                               #bloqueSentencia
    | SI PAR_IZQ expr PAR_DER sentencia (SINO sentencia)?                  #siSentencia
    | PARA PAR_IZQ (declaracion | expr PUNTOCOMA) expr? PUNTOCOMA expr? PAR_DER sentencia  #paraSentencia
    | LOP PAR_IZQ expr PAR_DER sentencia                              #LOPSentencia
    | HACER sentencia LOP PAR_IZQ expr PAR_DER PUNTOCOMA              #hacerLOPSentencia
    | RET expr? PUNTOCOMA                                                  #retornarSentencia
    | MOSTRAR PAR_IZQ args? PAR_DER PUNTOCOMA                               #MOSTRARSentencia
    ;

expr 
    : asignacion
    ;

asignacion
    : ID ASIGN asignacion          #asignacionExp
    | logicaOr                     #soloExp
    ;

logicaOr
    : logicaOr O logicaAnd         #opLogicaOR
    | logicaAnd                    #soloLogicaAnd
    ;

logicaAnd
    : logicaAnd Y igualdad         #opLogicaAND
    | igualdad                     #soloIgualdad
    ;

igualdad
    : igualdad (IGUAL | DIF) comparacion   #opIgualdadDiferencia
    | comparacion                         #soloComparacion
    ;

comparacion
    : comparacion (MENOR | MAYOR | MEN_IGUAL | MAY_IGUAL) suma   #opComparacion
    | suma                                                       #soloSuma
    ;

suma
    : suma (SUMA | RESTA) mult     #opSumaResta
    | mult                         #soloMult
    ;

mult
    : mult (MULT | DIV | RESIDUO) potencia   #opMultDiv
    | potencia                     #soloPotencia
    ;

potencia
    : unario POTENCIA potencia     #opPotencia
    | unario                       #soloUnario
    ;

unario
    : NOT unario                   #opUnarioNot
    | SUMA unario                  #opUnarioPositivo
    | RESTA unario                 #opUnarioNegativo
    | llamada                      #llamadaUnaria
    ;

llamada
    : primary (PAR_IZQ args? PAR_DER)*   #llamadaFuncion
    ;

primary
    : PAR_IZQ expr PAR_DER         #parentesis
    | NUMERO                       #numero
    | BOOL_LIT                     #booleano
    | TEXTO                        #texto
    | ID                           #variable
    ;

args
    : expr (COMA expr)*            #argumentos
    ;

tipo
    : ENTERO    #tipoEntero
    | DECIMAL   #tipoDecimal
    | BOOL      #tipoBool
    | CADENA    #tipoCadena
    | VOID      #tipoVoid
    ;
