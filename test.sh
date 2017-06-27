#!/bin/bash -e
# <copyright>
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>


echo "Test tiered locking case"
csmake --debug --makefile test.csmake clean
for x in {1..100}
do
    csmake --debug --makefile test.csmake test&
done
wait
if [ "10000" == `cat target/counter` ]
then
    echo "Test successful"
else
    echo "XXX Test failed XXX"
    test False
fi

echo "Test flat locking case"
csmake --debug --makefile test.csmake clean
for x in {1..100}
do
    csmake --debug --makefile test.csmake --command=many test&
done
wait
if [ "10000" == `cat target/counter` ]
then
    echo "Test successful"
else
    echo "XXX Test failed XXX"
    test False
fi

#See what it does without the locking - it's ugly...
#csmake --debug --makefile test.csmake clean
#for x in {1..100}
#do
#    csmake --debug --makefile test.csmake messup&
#done

