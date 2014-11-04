#!/bin/bash
USRBIN=${HOME}/local/bin


if [[ ":${PATH}:" == *":${USRBIN}:"* ]]; then 
	echo $USRBIN already in path
else
	echo adding $USRBIN to your path in .bashrc and appending to '$PATH' now
	echo 'export PATH=$PATH:'$USRBIN >> $HOME/.bashrc
    export PATH=$PATH:$USRBIN 
fi
