#ifndef TS_KERNELS_DIV_H
#define TS_KERNELS_DIV_H

#include <global/operator_factory.h>
#include <core/tensor.h>
#include <runtime/stack.h>



namespace ts {


class Div : public ts::Operator {
public:

    using supper = ts::Operator;
    Div();

    virtual void init(); 

    virtual int run(ts::Stack &stack);
    virtual int infer(ts::Stack &stack, std::vector<ts::Tensor::Prototype> &output); 


private:
    template<typename T>
    void dimshuffle(const Shape & shape, int dim, int div_dim, const T* src, T* dst);

    template<typename T>
    void compute_div(ts::Tensor *input_tensor, ts::Tensor *div_tensor, ts::Tensor *output_tensor);
    void infer_private(ts::Stack &stack, ts::Tensor::Prototype &output);


};




}

#endif