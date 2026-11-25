import numpy as np
import pytest
from cst_automation.touchstone import write_touchstone
from cst_automation import embedded_network as embedded

@pytest.mark.parametrize('n', [2,3,11])
def test_touchstone_v1_rows_and_independent_matrix_reconstruction(tmp_path,n):
    matrix=np.array([[[complex(100*i+j, -100*i-j) for j in range(n)] for i in range(n)]])
    path=tmp_path/f'a.s{n}p'
    write_touchstone(path,[2.5],matrix,50,frequency_unit='Hz')
    lines=[x.split() for x in path.read_text().splitlines()[1:]]
    if n==2:
        assert len(lines)==1 and len(lines[0])==9
        assert [float(x) for x in lines[0][1::2]]==[0,100,1,101]
    else:
        chunks=(n+3)//4
        assert len(lines)==n*chunks
        for row in range(n):
            data=[]
            for chunk in range(chunks):
                tokens=lines[row*chunks+chunk]
                if row==0 and chunk==0: assert float(tokens.pop(0))==2.5
                assert len(tokens)==2*min(4,n-4*chunk)
                data.extend(complex(float(tokens[k]),float(tokens[k+1])) for k in range(0,len(tokens),2))
            assert data==[complex(100*row+j,-100*row-j) for j in range(n)]
    f,s=embedded.read_touchstone(path,n,50)
    assert f.tolist()==[2.5] and np.array_equal(s,matrix)

@pytest.mark.parametrize('n',[3,11])
def test_embedded_writer_complies_with_multiline_v1_and_reads(tmp_path,n):
    matrix=np.array([[[complex(100*i+j,j-i) for j in range(n)] for i in range(n)]])
    path=tmp_path/f'b.s{n}p'
    embedded.write_touchstone(path,[1.0],matrix,75)
    lines=path.read_text().splitlines()[1:]
    assert len(lines)==n*((n+3)//4)
    assert max(len(line.split()) for line in lines)<=9
    _,actual=embedded.read_touchstone(path,n,75)
    assert np.array_equal(actual,matrix)
